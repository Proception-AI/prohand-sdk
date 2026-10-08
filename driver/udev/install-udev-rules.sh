#!/usr/bin/env bash
# Standalone udev-rules installer for the Proception SDK Linux driver bundle.
#
# Self-contained (no `just`, no cross-dir sourcing) so it ships inside the
# published pro-sdk driver package. Installs every `*.rules` file sitting
# beside this script into /etc/udev/rules.d/, then reloads and triggers udev
# so the ProHand / ProGlove USB devices are accessible without sudo.
#
# In the pro-sdk distribution this lives at driver/udev/ next to
# 60-prohand.rules and 60-proglove.rules.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="/etc/udev/rules.d"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

show_help() {
  cat << EOF
Usage: $(basename "$0") [options]

Install udev rules for Proception (ProHand / ProGlove) USB devices on Linux.
Grants raw-USB and serial-port access without sudo.

Options:
    -h, --help     Show this help
    -c, --check    Report install status without changing anything
    -r, --remove   Remove the installed Proception rules
    -f, --force    Overwrite existing rules even if unchanged
    -v, --verbose  Print each rules file as it is installed

Arguments:
    [SOURCE...]    Rules files or directories to install. With none given,
                   defaults to every *.rules file next to this script (the
                   pro-sdk distribution layout). A directory contributes its
                   *.rules; a file is used directly.

Installs into ${DEST_DIR}/. After install: unplug/replug the device
(ProHand/ProGlove uses the CP210x or STM32 CDC-ACM interface).
EOF
}

# Populate RULES_FILES from the given sources (files or dirs). With no sources,
# defaults to *.rules beside this script (distribution layout). Plain globbing
# (not `mapfile`) so it works on bash 3.2; the -e guard handles no-match.
RULES_FILES=()
collect_rules() {
  local sources=("$@")
  [ ${#sources[@]} -eq 0 ] && sources=("$SCRIPT_DIR")
  local s f
  for s in "${sources[@]}"; do
    if [ -d "$s" ]; then
      for f in "$s"/*.rules; do
        [ -e "$f" ] && RULES_FILES+=("$f")
      done
    elif [ -f "$s" ]; then
      RULES_FILES+=("$s")
    else
      echo -e "${YELLOW}⚠ rules source not found: $s${NC}"
    fi
  done
}

require_linux() {
  if [[ "$(uname -s)" != "Linux" ]]; then
    echo -e "${RED}Error: udev rules apply to Linux only (current OS: $(uname -s)).${NC}"
    exit 1
  fi
}

require_rules_present() {
  if [[ ${#RULES_FILES[@]} -eq 0 ]]; then
    echo -e "${RED}Error: no .rules files found next to ${SCRIPT_DIR}.${NC}"
    exit 1
  fi
}

check_status() {
  echo -e "${BLUE}Proception udev rules status${NC}"
  for src in "${RULES_FILES[@]}"; do
    local dest
    dest="${DEST_DIR}/$(basename "$src")"
    if [[ -f "$dest" ]]; then
      if diff -q "$src" "$dest" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ $(basename "$src") installed (up to date)${NC}"
      else
        echo -e "  ${YELLOW}⚠ $(basename "$src") installed but differs — run with --force${NC}"
      fi
    else
      echo -e "  ${YELLOW}✗ $(basename "$src") not installed${NC}"
    fi
  done
}

reload_udev() {
  echo "Reloading udev rules..."
  sudo udevadm control --reload-rules
  sudo udevadm trigger
  echo -e "${GREEN}✓ udev reloaded${NC}"
}

install_rules() {
  local force="$1" verbose="$2" changed=0
  echo -e "${BLUE}Installing udev rules to ${DEST_DIR}/...${NC}"
  sudo mkdir -p "$DEST_DIR"
  for src in "${RULES_FILES[@]}"; do
    local dest
    dest="${DEST_DIR}/$(basename "$src")"
    if [[ -f "$dest" && "$force" != "true" ]] && diff -q "$src" "$dest" > /dev/null 2>&1; then
      echo -e "  ${GREEN}✓ $(basename "$src") already up to date${NC}"
      continue
    fi
    [[ "$verbose" == "true" ]] && {
      echo "── $src ──"
      cat "$src"
      echo "──"
    }
    sudo cp "$src" "$dest"
    echo -e "  ${GREEN}✓ installed $(basename "$src")${NC}"
    changed=1
  done
  if [[ "$changed" -eq 1 ]]; then
    reload_udev
    echo ""
    echo -e "${GREEN}Done. Unplug and replug your device to apply.${NC}"
  else
    echo -e "${GREEN}Nothing to do — all rules current.${NC}"
  fi
}

remove_rules() {
  echo -e "${BLUE}Removing Proception udev rules...${NC}"
  local removed=0
  for src in "${RULES_FILES[@]}"; do
    local dest
    dest="${DEST_DIR}/$(basename "$src")"
    if [[ -f "$dest" ]]; then
      sudo rm -f "$dest"
      echo -e "  ${GREEN}✓ removed $(basename "$src")${NC}"
      removed=1
    fi
  done
  if [[ "$removed" -eq 1 ]]; then
    reload_udev
  else
    echo -e "${YELLOW}No installed Proception rules found.${NC}"
  fi
}

main() {
  local force="false" check_only="false" remove="false" verbose="false"
  local sources=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h | --help)
        show_help
        exit 0
        ;;
      -c | --check)
        check_only="true"
        shift
        ;;
      -r | --remove)
        remove="true"
        shift
        ;;
      -f | --force)
        force="true"
        shift
        ;;
      -v | --verbose)
        verbose="true"
        shift
        ;;
      -*)
        echo -e "${RED}Unknown option: $1${NC}"
        show_help
        exit 1
        ;;
      *)
        sources+=("$1")
        shift
        ;;
    esac
  done

  require_linux
  if [ ${#sources[@]} -eq 0 ]; then collect_rules; else collect_rules "${sources[@]}"; fi
  require_rules_present

  if [[ "$check_only" == "true" ]]; then
    check_status
  elif [[ "$remove" == "true" ]]; then
    remove_rules
  else
    install_rules "$force" "$verbose"
  fi
}

main "$@"
