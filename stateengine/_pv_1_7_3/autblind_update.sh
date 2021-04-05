#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"
SCRIPTSYSTEM=$(uname -a)
stringContain() { [ -z "${2##*$1*}" ] && { [ -z "$1" ] || [ -n "$2" ] ;} ; }
items_mac () {
echo "Updating item yaml on Mac OS X"
sudo sed -i {} 's/as_/se_/g' ../../items/*.yaml 2>&1
sudo sed -i {} 's/autostate_/stateengine_/g' ../../items/*.yaml 2>&1
sudo sed -i {} 's/autoblind/stateengine/g' ../../items/*.yaml 2>&1
}

items_linux () {
echo "Updating item yaml on Linux"
sudo sed -i 's/as_/se_/g' ../../items/*.yaml 2>&1
sudo sed -i 's/autostate_/stateengine_/g' ../../items/*.yaml 2>&1
sudo sed -i 's/autoblind/stateengine/g' ../../items/*.yaml 2>&1
}

update_items () {
  if stringContain 'Darwin' $SCRIPTSYSTEM; then items_mac; else items_linux; fi
}

logics_mac () {
echo "Updating logics on Mac OS X"
sudo sed -i {} 's/autostate_/stateengine_/g' ../../logics/*.py 2>&1
sudo sed -i {} 's/autoblind/stateengine/g' ../../logics/*.py 2>&1
}

logics_linux () {
echo "Updating logics on Linux"
sudo sed -i 's/autostate_/stateengine_/g' ../../logics/*.py 2>&1
sudo sed -i 's/autoblind/stateengine/g' ../../logics/*.py 2>&1
}

update_logics () {
  if stringContain 'Darwin' $SCRIPTSYSTEM; then logics_mac; else logics_linux; fi
}

rename_files () {
find ../../var/cache/ -type f -name '*autoblind*' -exec bash -c 'mv "$0" "${0/\autoblind/stateengine}"' {} \;
find ../../var/cache/ -type f -name '*autostate*' -exec bash -c 'mv "$0" "${0/\autostate/stateengine}"' {} \;
}

cd $DIR
echo "Changed to directory: $DIR. Running on $SCRIPTSYSTEM"
echo "This script replaces as_* entries by se_* entries, autostate and autoblind entries by stateengine."
  echo "Do you want to update all item yaml files?"
  select rerun in "Update" "Skip"; do
      case $rerun in
          "Update" ) update_items;break;;
          "Skip" ) echo "Skipping"; break;;
          *) echo "Skipping"; break;;
      esac
  done
  echo "Do you want to update your logics files and replace autostate/autoblind entries by stateengine?"
  select rerun in "Update" "Skip"; do
      case $rerun in
          "Update" ) update_logics;break;;
          "Skip" ) echo "Skipping"; break;;
          *) echo "Skipping"; break;;
      esac
  done
echo ""
echo "This script renames all cache files including autoblind or autostate to stateengine"
  echo "Do you want to rename cache files?"
  select rerun in "Rename" "Skip"; do
      case $rerun in
          "Rename" ) rename_files;break;;
          "Skip" ) echo "Skipping"; break;;
          *) echo "Skipping"; break;;
      esac
  done
