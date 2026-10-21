# Builds 42/media/java/client/SkyhammerAircraft3D.jar from this folder.
# Usage: powershell -ExecutionPolicy Bypass -File build.ps1 [-Ecj <ecj jar>]
# Compiles with the Eclipse compiler (ecj) on the game's own Java (PZ classes are Java 25), so no
# JDK is needed; output targets Java 17.
param([string]$Ecj = "C:\Users\user\Documents\Codex\2026-09-30\w\work\ecj-3.43.0.jar")
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$mod = Resolve-Path "$here\..\.."
$pz = "C:\Program Files (x86)\Steam\steamapps\common\ProjectZomboid"
$java = "$pz\jre64\bin\java.exe"
$viewpoint = "C:\Program Files (x86)\Steam\steamapps\workshop\content\108600\3809306528\mods\Viewpoint\42\media\java\client\Viewpoint.jar"
$cp = "$pz;$pz\projectzomboid.jar;$pz\ZombieBuddy.jar;$viewpoint"
$out = Join-Path $env:TEMP ("skyhammer-java-build-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force "$out\classes\skyhammer\aircraft", "$out\classes\META-INF" | Out-Null

$sources = Get-ChildItem "$here\skyhammer\aircraft\*.java" | ForEach-Object FullName
& $java -jar $Ecj -17 -encoding UTF-8 -nowarn -cp $cp -d "$out\classes" @sources
if ($LASTEXITCODE -ne 0) { throw "ecj failed" }
foreach ($res in "ac130.mesh", "aircraft.vert", "aircraft.frag", "apache.mesh", "apache.vert", "apache.frag", "b2.mesh", "bomber.frag", "a10.mesh", "a10.vert", "uh60.mesh", "uh60.vert", "napalm.mesh", "nuke.vert", "nuke.frag", "nuke_smoke_atlas.png", "angel.vert", "angel.frag") {
    Copy-Item "$here\skyhammer\aircraft\$res" "$out\classes\skyhammer\aircraft\$res"
}
Set-Content "$out\classes\META-INF\MANIFEST.MF" "Manifest-Version: 1.0`r`nCreated-By: Skyhammer build.ps1`r`n" -Encoding ascii -NoNewline

# Entry names need "/" separators (ZipFile.CreateFromDirectory on .NET Framework writes "\").
Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
$tmpJar = "$out\SkyhammerAircraft3D.jar"
$root = (Resolve-Path "$out\classes").Path.TrimEnd('\') + '\'
$zip = [IO.Compression.ZipFile]::Open($tmpJar, [IO.Compression.ZipArchiveMode]::Create)
try {
    $zip.CreateEntry("META-INF/") | Out-Null
    [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, "$out\classes\META-INF\MANIFEST.MF", "META-INF/MANIFEST.MF") | Out-Null
    # (directory entries too, as the JDK's jar tool writes them: a package lookup by resource needs them)
    Get-ChildItem "$out\classes" -Recurse -Directory | Where-Object { $_.Name -ne "META-INF" } | ForEach-Object {
        $zip.CreateEntry($_.FullName.Substring($root.Length).Replace('\', '/') + "/") | Out-Null
    }
    Get-ChildItem "$out\classes" -Recurse -File | Where-Object { $_.Name -ne "MANIFEST.MF" } | ForEach-Object {
        $name = $_.FullName.Substring($root.Length).Replace('\', '/')
        [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $_.FullName, $name) | Out-Null
    }
} finally { $zip.Dispose() }
$jar = "$mod\42\media\java\client\SkyhammerAircraft3D.jar"
if (Test-Path -LiteralPath $jar) {
    $stale = Join-Path "$mod\source\stale" ("java-" + (Get-Date -Format "yyyyMMdd-HHmmss-ffff"))
    New-Item -ItemType Directory -Path $stale -Force | Out-Null
    Copy-Item -LiteralPath $jar -Destination (Join-Path $stale "SkyhammerAircraft3D.jar")
}
Copy-Item $tmpJar $jar -Force
"built $jar  sha256 $((Get-FileHash $jar).Hash)"
