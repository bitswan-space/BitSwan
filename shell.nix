let pkgs = import <nixpkgs> {};

in pkgs.mkShell {
    buildInputs = with pkgs; [
        python311
        python311Packages.setuptools
        python311Packages.pip
        python311Packages.virtualenv
        python311Packages.wheel
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

