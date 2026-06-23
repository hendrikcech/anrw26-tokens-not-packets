{
  description = "Build quicheperf with crane";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    crane.url = "github:ipetkov/crane";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, crane, flake-utils, ... }:
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
            (builtins.match ".*\\.yml$" path != null);
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

        quicheperf = craneLib.buildPackage (commonArgs // {
          inherit cargoArtifacts;
        });

      in
      {
        packages = {
          default = quicheperf;
          quicheperf = quicheperf;
        };

        apps.default = flake-utils.lib.mkApp {
          drv = quicheperf;
        };

        devShells.default = craneLib.devShell {
          inputsFrom = [ quicheperf ];
          packages = with pkgs; [
            cargo
            rustc
            rustfmt
            clippy
          ];
        };
      }
    );
}
