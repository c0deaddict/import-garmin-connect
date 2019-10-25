with import <nixpkgs> {};

mkShell {
  buildInputs = [
    python3
  ] ++ (with python3Packages; [
    requests
    influxdb
  ]);
}
