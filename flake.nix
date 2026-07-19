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

        # Start Open vSwitch (ovsdb-server + ovs-vswitchd) unless already up.
        #
        # mininet's default switch (OVSSwitch) talks to ovsdb-server over
        # /var/run/openvswitch/db.sock. The NixOS VM this runs in provides the
        # openvswitch package but defines no openvswitch service, so the daemons
        # have to be bootstrapped. Without them mininet fails with
        # "database connection failed (No such file or directory)".
        #
        # Called from shellHook, so it must be safe to run repeatedly and must
        # never abort the shell: the DB is created once, each daemon is started
        # only if down, and failures degrade to a warning.
        ovs-up = pkgs.writeShellScriptBin "ovs-up" ''
          set -eu

          ovs=${pkgs.openvswitch}
          db=/var/lib/openvswitch/conf.db
          rundir=/var/run/openvswitch
          logdir=/var/log/openvswitch

          # Already up: stay quiet so it does not spam every shell entry.
          if pgrep -x ovsdb-server >/dev/null && pgrep -x ovs-vswitchd >/dev/null; then
              exit 0
          fi

          echo "Starting Open vSwitch (needed by mininet)..." >&2

          sudo modprobe openvswitch
          sudo mkdir -p "$rundir" "$(dirname "$db")" "$logdir"

          if [ ! -f "$db" ]; then
              sudo $ovs/bin/ovsdb-tool create "$db" \
                  $ovs/share/openvswitch/vswitch.ovsschema
          fi

          if ! pgrep -x ovsdb-server >/dev/null; then
              sudo $ovs/bin/ovsdb-server "$db" \
                  --remote=punix:"$rundir/db.sock" \
                  --remote=db:Open_vSwitch,Open_vSwitch,manager_options \
                  --pidfile="$rundir/ovsdb-server.pid" \
                  --detach --log-file="$logdir/ovsdb-server.log"
          fi

          sudo $ovs/bin/ovs-vsctl --no-wait init

          if ! pgrep -x ovs-vswitchd >/dev/null; then
              sudo $ovs/bin/ovs-vswitchd \
                  --pidfile="$rundir/ovs-vswitchd.pid" \
                  --detach --log-file="$logdir/ovs-vswitchd.log"
          fi

          # ovs-vsctl needs root: db.sock is root-owned. mininet also runs as root.
          sudo $ovs/bin/ovs-vsctl show >/dev/null
          echo "Open vSwitch is running" >&2
        '';

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
          ]
          # Also exposed as a command so it can be re-run by hand after a reboot.
          ++ lib.optionals stdenv.isLinux [ ovs-up ];

          # mininet needs the Open vSwitch daemons running. Bootstrap them on
          # shell entry so `task mn-run:*` just works. Linux-only (there is no
          # mininet/OVS story on darwin), and a failure here must not stop you
          # from entering the shell for e.g. plotting.
          shellHook = pkgs.lib.optionalString pkgs.stdenv.isLinux ''
            ${ovs-up}/bin/ovs-up \
              || echo "warning: Open vSwitch not started; mininet experiments will fail" >&2
          '';
        };
      }
    );
}
