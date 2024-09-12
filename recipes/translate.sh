#!/usr/bin/env bash
XMI="../Gemeentelijk-Gegevensmodel/Gemeentelijk Gegevensmodel XMI2.1.xml"
GGM="../Gemeentelijk-Gegevensmodel/Gemeentelijk Gegevensmodel EA16.qea"
ROOT_GGM=EAPK_073A3334_C42A_41a6_A0C6_38DFF8C70236
i18N_FILE=./ggm.i18n.json


echo "Script to read datamodel from $XMI and generate JSON Schema and Markdown documentation for the version entered on the command line"

# Check if the version parameter is provided
if [ -z "$1" ]; then
    echo "Please provide the language to which the GGM needs to be translated."
    exit 1
fi
LANG="$1"
TRANSLATION_SCHEMA=translation_$LANG

# Maak de nieuw GGM aan en Strip het pad en de extensie van de bestandsnaam
filename="${GGM%.*}"        # Verwijdert de extensie
extension="${GGM##*.}"      # Pak de extensie
output_filename="${filename}-${LANG}.${extension}"

# Controleer of het temp.md.template bestand bestaat
if [ ! -f "$i18N_FILE" ]; then
    echo "File $i18N_FILE does not exist."
    exit 1
fi

# Check if python ./crunch_uml/cli.py is installed
if ! command -v python ./crunch_uml/cli.py &> /dev/null; then
    echo "This tool makes use of python ./crunch_uml/cli.py, but is not installed. Please install python ./crunch_uml/cli.py before proceeding. See: https://github.com/brienen/python ./crunch_uml/cli.py"
    exit 1
fi

# First read the XMI
echo "Reading GGM Datamodel $XMI..."
python ./crunch_uml/cli.py import -f "$XMI" -t eaxmi -db_create

# Peform transformation and move schuldhulp module to crunch-schema 'schuldhulp_informatiemodel'
echo "Copy GGM from default schema to schema $LANG..."
python ./crunch_uml/cli.py transform -ttp copy -sch_to $TRANSLATION_SCHEMA --root_package $ROOT_GGM 

# Peform transformation and move schuldhulp module to crunch-schema 'schuldhulp_informatiemodel'
echo "Reading translation for $LANG from file $i18N_FILE into schema $TRANSLATION_SCHEMA..."
python ./crunch_uml/cli.py -sch $TRANSLATION_SCHEMA import -f $i18N_FILE -t i18n --language $LANG

# Maak copy van GGM voor vertaling
echo "Maak een kopie van het GGM voor vertaling naar bestand $output_filename..."
cp "$GGM" "$output_filename"

# Write the translation to the GGM copy
echo "Writing translation for $LANG to file $output_filename..."
python ./crunch_uml/cli.py -sch $TRANSLATION_SCHEMA export -f "$output_filename" -t earepo --tag_strategy update


#["export", "-f", EA_DB, "-t", "earepo", "--tag_strategy", "update"]


# Replace placeholders in uitwisselspecificatie.md.template with version
#sed "s/###VERSION###/$version/g" "$i18N_FILE" > "$UITWISSEL_MD"

# Generate mkdcos documentation for new version
#mkdocs build
# Add new version to documentation tree
#mike deploy $version
# Set new version as default
#mike set-default $version 
# Deploy documentation
# git push origin gh-pages