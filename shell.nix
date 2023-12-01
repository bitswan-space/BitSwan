let pkgs = import <nixpkgs> {};

in pkgs.mkShell {
    buildInputs = with pkgs; [
        python310
        python310Packages.setuptools
        python310Packages.pip
        python310Packages.virtualenv
        python310Packages.wheel
        stdenv.cc.cc.lib
        autoconf
        automake
        libtool
    ];

  shellHook = ''
    export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib";
    source venv/bin/activate
  '';

}

