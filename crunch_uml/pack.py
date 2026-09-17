"""``crunch_uml pack``: turn an EA model file into a row artifact (``.cua.gz``).

detect (content, not extension) -> parse into a fresh temporary SQLite ->
write the artifact with the standard-library writer (:mod:`crunch_uml.artifact`)
-> remove the temporary database.

The command always prints exactly one JSON line on stdout; logging goes to
stderr. Exit codes:

* ``0`` - artifact written;
* ``2`` - the input was refused or holds no usable model; ``code`` is one of
  ``file_type_unknown``, ``xmi_not_ea``, ``xml_malformed``, ``xml_forbidden``,
  ``qea_unreadable``, ``model_empty``, ``parse_oom``;
* ``1`` - unexpected failure (``parse_failed``).

A parse always goes to its own fresh SQLite file, never to a shared database:
that keeps it on the fast insert path and makes the run marker unambiguous.
"""

import argparse
import gc
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import tempfile

import sqlalchemy.exc
from lxml import etree

import crunch_uml.db as db
import crunch_uml.schema as sch
from crunch_uml import artifact, const, detect, xmlsafe
from crunch_uml._version import __version__, producer_build
from crunch_uml.parsers.parser import ParserRegistry

logger = logging.getLogger()

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_REFUSED = 2

CODE_MODEL_EMPTY = "model_empty"
CODE_PARSE_OOM = "parse_oom"
CODE_PARSE_FAILED = "parse_failed"

PACKABLE_FORMATS = (detect.FORMAT_EAXMI, detect.FORMAT_QEA)
CAPABILITIES = {
    detect.FORMAT_EAXMI: {"geometry": True, "tags": True, "stereotypes": True},
    detect.FORMAT_QEA: {"geometry": True, "tags": True, "stereotypes": True},
}


class PackError(Exception):
    def __init__(self, code, message, exit_code=EXIT_REFUSED):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


def add_args(argumentparser, subparser_dict):
    pack_parser = subparser_dict.get(const.CMD_PACK)
    pack_parser.add_argument("-f", "--inputfile", type=str, required=True, help="EA model file (.qea or EA-XMI 2.1)")
    pack_parser.add_argument(
        "-t",
        "--inputtype",
        type=str,
        choices=PACKABLE_FORMATS,
        help="Expected format; refused when the detected format differs. Default: as detected.",
    )
    pack_parser.add_argument("-o", "--outputfile", type=str, required=True, help="Artifact to write (.cua.gz)")

    detect_parser = subparser_dict.get(const.CMD_DETECT)
    detect_parser.add_argument("-f", "--inputfile", type=str, required=True, help="File to classify")


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class _IsolatedDatabase:
    """A crunch_uml Database on its own SQLite file for the duration of a ``with``.

    ``Database`` is a process-wide singleton; the previous instance (if any) is
    set aside and restored afterwards, so a pack never writes into whatever
    database the process had open.
    """

    def __init__(self, path):
        self._url = f"sqlite:///{path}"
        self._previous = None
        self.database = None

    def __enter__(self):
        self._previous = db.Database._instance
        db.Database._instance = None
        self.database = db.Database(self._url, db_create=True, on_version_mismatch=const.VERSION_MISMATCH_RECREATE)
        return self.database

    def __exit__(self, *exc):
        try:
            if self.database is not None:
                self.database.session.close()
                self.database.engine.dispose()
        finally:
            db.Database._instance = self._previous
        return False


def _parse(source, fmt, sqlite_path):
    """Parse ``source`` into the SQLite file; returns the class count."""
    with _IsolatedDatabase(sqlite_path) as database:
        schema = sch.Schema(database, schema_name=const.DEFAULT_SCHEMA)
        run_id = database.start_import_run(const.DEFAULT_SCHEMA)
        args = argparse.Namespace(inputfile=source, url=None, inputtype=fmt, skip_xmi_relations=False)
        try:
            ParserRegistry.getinstance(fmt).parse(args, schema)
            database.commit()
        except BaseException:
            database.rollback()
            raise
        database.complete_import_run(run_id)
        return schema.count_class() + schema.count_datatype()


def pack(inputfile, outputfile, inputtype=None):
    """Run the pack pipeline; returns ``(exit_code, result_dict)``. Never raises for bad input."""
    work_dir = None
    try:
        if not os.path.isfile(inputfile):
            raise PackError(detect.CODE_FILE_TYPE_UNKNOWN, "input file does not exist")
        detection = detect.detect(inputfile)
        fmt = detection["format"]
        if not detection["accepted"] or fmt not in PACKABLE_FORMATS:
            raise PackError(
                detection["code"] or detect.CODE_FILE_TYPE_UNKNOWN,
                f"input refused: detected as {detection['verdict']}",
            )
        if inputtype and inputtype != fmt:
            raise PackError(detect.CODE_FILE_TYPE_UNKNOWN, f"expected {inputtype}, detected {fmt}")

        source = {
            "detected_format": fmt,
            "exporter": detection["exporter"],
            "exporter_version": detection["exporter_version"],
            "xmi_version": detection["xmi_version"],
            "sha256": _sha256(inputfile),
            "size": detection["size"],
        }

        work_dir = tempfile.mkdtemp(prefix="crunch_pack_")
        sqlite_path = os.path.join(work_dir, "parse.db")
        try:
            classes = _parse(inputfile, fmt, sqlite_path)
        except xmlsafe.XMLForbiddenError as e:
            raise PackError(detect.CODE_XML_FORBIDDEN, str(e))
        except (etree.XMLSyntaxError, UnicodeError) as e:
            raise PackError(detect.CODE_XML_MALFORMED, str(e))
        except RuntimeError as e:
            if fmt == detect.FORMAT_EAXMI and "XMI inlezen" in str(e):
                raise PackError(detect.CODE_XML_MALFORMED, str(e))
            raise
        except (sqlite3.DatabaseError, sqlalchemy.exc.DatabaseError) as e:
            if fmt == detect.FORMAT_QEA:
                raise PackError(detect.CODE_QEA_UNREADABLE, str(e))
            raise
        gc.collect()
        if classes == 0:
            raise PackError(CODE_MODEL_EMPTY, "the model contains no classes")

        partial = outputfile + ".partial"
        counts = artifact.write_artifact(
            sqlite_path,
            partial,
            tables=db.getTables(),
            producer={"crunch_version": __version__, "producer_build": producer_build()},
            source=source,
            capabilities=CAPABILITIES[fmt],
        )
        os.replace(partial, outputfile)
        return EXIT_OK, {
            "status": "ok",
            "output": outputfile,
            "detected_format": fmt,
            "crunch_version": __version__,
            "sha256": source["sha256"],
            "counts": counts,
        }
    except PackError as e:
        logger.error(f"pack refused ({e.code}): {e}")
        return e.exit_code, {"status": "error", "code": e.code, "message": str(e)}
    except MemoryError:
        logger.error("pack ran out of memory")
        return EXIT_REFUSED, {"status": "error", "code": CODE_PARSE_OOM, "message": "out of memory"}
    except Exception as e:  # noqa: BLE001 - the command must always answer with a code
        logger.exception("pack failed")
        return EXIT_FAILED, {"status": "error", "code": CODE_PARSE_FAILED, "message": f"{type(e).__name__}: {e}"}
    finally:
        if work_dir is not None:
            shutil.rmtree(work_dir, ignore_errors=True)
        partial = outputfile + ".partial"
        if os.path.exists(partial):
            os.remove(partial)


def run_pack(args):
    exit_code, result = pack(args.inputfile, args.outputfile, args.inputtype)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return exit_code


def run_detect(args):
    if not os.path.isfile(args.inputfile):
        print(json.dumps({"status": "error", "code": detect.CODE_FILE_TYPE_UNKNOWN, "message": "no such file"}))
        return EXIT_FAILED
    result = detect.detect(args.inputfile)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return EXIT_OK if result["accepted"] else EXIT_REFUSED
