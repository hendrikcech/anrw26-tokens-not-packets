{
  description = "Emulation harness and analysis for the ANRW'26 tokens-not-packets paper";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    # quicheperf.url = "github:hendrikcech/quicheperf";
    quicheperf.url = "git+ssh://git@github.com/hendrikcech/quicheperf?ref=main";
  };

  outputs = { self, nixpkgs, flake-utils, quicheperf, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };

        quicheperf_pkg = quicheperf.packages.${system}.default;

        pysimdjson_pkg = pkgs.python3Packages.buildPythonPackage rec {
          pname = "pysimdjson";
          version = "7.0.2";
          pyproject = true;
          src = pkgs.python3Packages.fetchPypi {
            inherit pname version;
            hash = "sha256-RM8nbkiRKjucfKNiwU2oQgp6wVqfGhbslb7P+G2zkEo=";
          };
          build-system = [ pkgs.python3Packages.setuptools pkgs.python3Packages.pybind11 pkgs.python3Packages.cython ];
        };

        pythonEnv = pkgs.python3.withPackages (ps: with ps; [
          matplotlib
          numpy
          pandas
          pysimdjson_pkg
          zstandard
          tqdm
          scipy
          mininet-python
        ]);

        sudo-wrapper = pkgs.writeShellScriptBin "sudo" ''
          if [ -x /run/wrappers/bin/sudo ]; then
            REAL_SUDO=/run/wrappers/bin/sudo
          elif [ -x /usr/bin/sudo ]; then
            REAL_SUDO=/usr/bin/sudo
          else
            echo "sudo-wrapper: Could not find system sudo" >&2
            exit 1
          fi

          # Parse sudo options to correctly place env PATH=$PATH before the command
          args=()
          while [[ $# -gt 0 ]]; do
              case "$1" in
                  -C|-g|-h|-p|-R|-r|-T|-t|-U|-u|--close-from|--group|--host|--prompt|--chroot|--role|--command-timeout|--type|--other-user|--user)
                      args+=("$1" "$2")
                      shift 2
                      ;;
                  --*=*)
                      args+=("$1")
                      shift
                      ;;
                  --)
                      args+=("$1")
                      shift
                      break
                      ;;
                  -*)
                      args+=("$1")
                      shift
                      ;;
                  *)
                      break
                      ;;
              esac
          done

          # Pass -E to preserve other environment variables (like PYTHONPATH)
          # Explicitly invoke `env PATH=$PATH` to defeat `secure_path` in sudoers
          if [ $# -eq 0 ]; then
              exec "$REAL_SUDO" -E "''${args[@]}"
          else
              exec "$REAL_SUDO" -E "''${args[@]}" env "PATH=$PATH" "$@"
          fi
        '';

      in
      {
        devShells.default = pkgs.mkShell {
          inputsFrom = [ quicheperf_pkg ];
          packages = with pkgs; [
            quicheperf_pkg
            pythonEnv
            mininet
            go-task
            bashInteractive
            sudo-wrapper

            # emu dependencies
            procps
            iproute2
            openvswitch
            inetutils
          ];
        };
      }
    );
}
