import glob
import os

from crunch_uml import cli


def test_markdown_monumenten_onderwijs():
    dir = "./test/output/"

    test_args = ["import", "-f", "./test/data/GGM_Monumenten_EA2.1.xml", "-t", "eaxmi", "-db_create"]
    cli.main(test_args)

    test_args = ["import", "-f", "./test/data/GGM_Onderwijs_XMI.2.1.xml", "-t", "xmi"]
    cli.main(test_args)

    test_args = [
        "export",
        "-t",
        "ggm_md",
        "-f",
        f"{dir}GGM.md",
        "--output_package_ids",
        "EAPK_F7651B45_2B64_4197_A6E5_BFC56EC98466,EAPK_CD9BF007_85C6_4af9_B3F4_2CAB5BF26B5E",
    ]
    cli.main(test_args)

    monfilename = f'{dir}GGM_Model Monumenten.md'
    assert os.path.exists(monfilename)
    assert open(monfilename, 'r').read().find('Status van de bescherming van een monument')
    assert open(monfilename, 'r').read().find('## Objecttype: Bouwactiviteit')

    onderwfilename = f'{dir}GGM_Model Onderwijs.md'
    assert os.path.exists(onderwfilename)
    assert open(monfilename, 'r').read().find('**Onderwijsloopbaan**')
    assert open(monfilename, 'r').read().find('## Objecttype: Leerling')

    # Cleanup
    for i in glob.glob('./test/output/*.md'):
        os.remove(i)
