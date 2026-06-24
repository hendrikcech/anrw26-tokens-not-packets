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

      in
      {
        packages = {
          default = quicheperf_pkg;
          quicheperf = quicheperf_pkg;
        };

        apps.default = flake-utils.lib.mkApp {
          drv = quicheperf_pkg;
        };

        apps.mn_runner = flake-utils.lib.mkApp {
          drv = pkgs.writeShellApplication {
            name = "mn_runner";
            runtimeInputs = with pkgs; [ pythonEnv ];
            text = ''
              export NIX_QUICHEPERF_EXE="${quicheperf_pkg}/bin/quicheperf"
              exec python3 "$PWD/mn_runner.py" "$@"
            '';
          };
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
            
            # mn-runner
            procps
            iproute2
            openvswitch
            inetutils
          ];
        };
      }
    );
}
