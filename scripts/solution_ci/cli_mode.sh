#!/usr/bin/env bash

archastro_cli_for_owner() {
  case "${1:-org}" in
    org)
      printf '%s\n' archagent
      ;;
    system)
      printf '%s\n' archastro
      ;;
    *)
      echo "Unknown owner: ${1:-} (expected org or system)" >&2
      return 2
      ;;
  esac
}
