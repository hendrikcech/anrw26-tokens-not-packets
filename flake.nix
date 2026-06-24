{
  description = "Build quicheperf with crane";

  inputs = {
    self.submodules = true;
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    crane.url = "github:ipetkov/crane";
    quicheperf = { url = "path:./quicheperf"; flake = false; };
    quiche = { url = "path:./quiche"; flake = false; };
  };

  outputs = { self, nixpkgs, flake-utils, crane, quicheperf, quiche, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };

        craneLib = crane.mkLib pkgs;

        # We need a custom filter because craneLib.cleanCargoSource will strip C/C++/CMake/Assembly/Go
        # files required by quiche's vendored boringssl.
        src = pkgs.lib.cleanSourceWith {
          src = craneLib.path ./.;
          filter = path: type:
            (craneLib.filterCargoSources path type) ||
            (builtins.match ".*\\.(c|cc|cpp|h|hpp|asm|S|cmake|go|pl|crt|key)$" path != null) ||
            (builtins.match ".*/CMakeLists\\.txt$" path != null) ||
            (builtins.match ".*/sources\\.cmake$" path != null) ||
            (builtins.match ".*\\.yml$" path != null) ||
            (type == "directory");
        };

        commonArgs = {
          inherit src;
          pname = "quicheperf";
          version = "0.1.0";
          strictDeps = true;
          cargoLock = ./quicheperf/Cargo.lock;
          sourceRoot = "source/quicheperf";

          nativeBuildInputs = with pkgs; [
            pkg-config
            cmake
            perl
            go
          ];

          buildInputs = with pkgs; [
          ];
        };
        
        # Build dependencies first to cache them
        cargoArtifacts = craneLib.buildDepsOnly commonArgs;

        quicheperf_pkg = craneLib.buildPackage (commonArgs // {
          inherit cargoArtifacts;
        });

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
        packages = {
          default = quicheperf_pkg;
          quicheperf = quicheperf_pkg;
        };

        apps.default = flake-utils.lib.mkApp {
          drv = quicheperf_pkg;
        };

        devShells.default = craneLib.devShell {
          inputsFrom = [ quicheperf_pkg ];
          packages = with pkgs; [
            quicheperf_pkg
            pythonEnv
            cargo
            rustc
            rustfmt
            clippy
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
