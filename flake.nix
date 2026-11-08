{
  description = "TinyBox packet radio BBS dev/run environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      forEachSystem = nixpkgs.lib.genAttrs [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
    in
    {
      devShells = forEachSystem (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python3.withPackages (ps: [
            ps.pyserial  # kisshub (serial KISS TNC)
            ps.pyyaml    # brocast
            # cbor2 is optional for brocast and not in nixpkgs under that
            # exact name on all channels; install with `pip install cbor2`
            # inside this shell if you need brocast's CBOR support.
          ]);
        in
        {
          default = pkgs.mkShell {
            packages = [ python ];
            shellHook = ''
              echo "TinyBox dev shell: $(python3 --version)"
              echo "Run the mailbox with:   python3 -m tinybox -c tinybox.conf"
              echo "Run the client with:    python3 -m tbclient -c tbclient.conf"
            '';
          };
        });
    };
}
