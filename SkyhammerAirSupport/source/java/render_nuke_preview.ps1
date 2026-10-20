$ErrorActionPreference = 'Stop'
$src = $PSScriptRoot
$out = Join-Path $src '..\fx_art'
$pz = 'C:\Program Files (x86)\Steam\steamapps\common\ProjectZomboid'
$java = Join-Path $pz 'jre64\bin\java.exe'
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$ecj = 'C:\Users\user\Documents\Codex\2026-09-30\w\work\ecj-3.43.0.jar'
New-Item -ItemType Directory -Force -Path "$out\preview_classes" | Out-Null
if (-not (Test-Path -LiteralPath "$out\nuke_smoke_atlas.png")) {
    & $python "$src\make_nuke.py"
    if ($LASTEXITCODE -ne 0) { throw 'Atlas generation failed' }
}
& $java -jar $ecj -17 -encoding UTF-8 -nowarn -cp "$pz;$pz\projectzomboid.jar" -d "$out\preview_classes" "$src\skyhammer\aircraft\Nuke.java" "$src\NukePreview.java" "$src\NukeGeometryTest.java"
if ($LASTEXITCODE -ne 0) { throw 'Preview compilation failed' }
& $java --enable-native-access=ALL-UNNAMED '-Djava.awt.headless=true' -cp "$out\preview_classes;$pz;$pz\projectzomboid.jar" NukePreview $src
if ($LASTEXITCODE -ne 0) { throw 'Preview render failed' }
& $java -cp "$out\preview_classes" NukeGeometryTest "$out\nuke_geometry_validation.json"
if ($LASTEXITCODE -ne 0) { throw 'Geometry validation failed' }
& $python "$src\make_nuke.py" --assemble
if ($LASTEXITCODE -ne 0) { throw 'Preview assembly failed' }
