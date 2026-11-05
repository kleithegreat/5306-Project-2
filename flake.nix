{
  description = "CS/INFO 5306 Project 2 — nowcasting state unemployment claims from Google Trends and Reddit";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/8ce4ef6cb6f871616146b9fe26d2a5ae594e94fe";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAll = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
      tex = pkgs: pkgs.texliveMedium.withPackages (ps: with ps; [
        acmart latexmk xstring totpages environ trimspaces hyperxmp ifmtarg ncctools
        libertine inconsolata newtx fontaxes comment preprint cmap kastrup upquote everyshi
      ]);
    in {
      apps = forAll (pkgs: {
        report = {
          type = "app";
          program = "${pkgs.writeShellApplication {
            name = "report";
            runtimeInputs = [ (tex pkgs) ];
            text = "latexmk -cd -pdf -interaction=nonstopmode paper/report.tex";
          }}/bin/report";
        };
      });

      devShells = forAll (pkgs: {
        default = pkgs.mkShell {
          name = "claims-nowcast";
          packages = [
            (pkgs.python3.withPackages (ps: with ps; [
              requests
              pandas
              pyarrow
              numpy
              scipy
              statsmodels
              matplotlib
              python-pptx
            ]))
            pkgs.poppler-utils
          ];
        };
      });
    };
}
