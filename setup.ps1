param (
    [switch]$uninstall
)

# --- CONFIGURATION ---
$AppName = "CROPPASS"
$AppFile = "croppass.py"
$InstallDir = Get-Location
$AppPath = "$InstallDir\$AppFile"
$WeightsDir = "$env:USERPROFILE\.deepface\weights"

# --- UNINSTALL LOGIC ---
if ($uninstall) {
    Write-Host "[CLEANUP] Uninstalling $AppName..." -ForegroundColor Yellow
    $Desktop = [System.Environment]::GetFolderPath("Desktop")
    $StartMenu = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"
    
    if (Test-Path "$Desktop\$AppName.lnk") { Remove-Item "$Desktop\$AppName.lnk" -Force }
    if (Test-Path "$StartMenu\$AppName.lnk") { Remove-Item "$StartMenu\$AppName.lnk" -Force }
    if (Test-Path "$WeightsDir\retinaface.h5") { Remove-Item "$WeightsDir\retinaface.h5" -Force }
    
    Write-Host "[CLEANUP] Removing Python libraries..." -ForegroundColor Cyan
    python -m pip uninstall -y deepface tf-keras opencv-python Pillow PyQt6 retina-face
    
    Write-Host "DONE: $AppName has been removed." -ForegroundColor Green
    Pause
    exit
}

# --- INSTALL LOGIC ---
Write-Host "[START] Setting up $AppName..." -ForegroundColor Cyan
$PythonVersion = "3.13.12"
$PythonURL = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe"

# 1. Install Python 3.13.12
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[1/5] Python not found. Downloading $PythonVersion..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $PythonURL -OutFile "$env:TEMP\py_inst.exe"
    Start-Process -FilePath "$env:TEMP\py_inst.exe" -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait
    Remove-Item "$env:TEMP\py_inst.exe"
    
    # Refresh PATH environment
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}

# 2. SELF-HEALING: Fix PIP if missing
Write-Host "[2/5] Verifying PIP installation..." -ForegroundColor Cyan
try {
    $pipTest = python -m pip --version 2>$null
    if (!$pipTest) { throw "Pip Missing" }
}
catch {
    Write-Host "WARNING: PIP is missing. Bootstrapping now..." -ForegroundColor Yellow
    python -m ensurepip --default-pip
    if (!(python -m pip --version 2>$null)) {
        Write-Host "Downloading get-pip.py from official source..." -ForegroundColor Yellow
        Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile "$env:TEMP\get-pip.py"
        python "$env:TEMP\get-pip.py"
        Remove-Item "$env:TEMP\get-pip.py"
    }
}

# 3. Install Libraries
Write-Host "[3/5] Installing Libraries..." -ForegroundColor Cyan
python -m pip install --upgrade pip
python -m pip install deepface tf-keras opencv-python Pillow PyQt6 retina-face numpy

# 4. Download Model
if (!(Test-Path $WeightsDir)) { New-Item -Path $WeightsDir -ItemType Directory -Force }
if (!(Test-Path "$WeightsDir\retinaface.h5")) {
    Write-Host "[4/5] Pre-downloading AI Model (RetinaFace)..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri "https://github.com/serengil/deepface_models/releases/download/v1.0/retinaface.h5" -OutFile "$WeightsDir\retinaface.h5"
}

# 5. Create Shortcuts
Write-Host "[5/5] Creating Shortcuts..." -ForegroundColor Cyan
$WScriptShell = New-Object -ComObject WScript.Shell
$DesktopLoc = [System.Environment]::GetFolderPath("Desktop")
$StartMenuLoc = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"

foreach ($Loc in @($DesktopLoc, $StartMenuLoc)) {
    $Shortcut = $WScriptShell.CreateShortcut("$Loc\$AppName.lnk")
    # $PythonW = (Get-Command pythonw).Source
    $PythonW = (Get-Command python).Source
    $Shortcut.TargetPath = $PythonW
    $Shortcut.Arguments = "`"$AppPath`""
    $Shortcut.WorkingDirectory = "$InstallDir"
    $Shortcut.IconLocation = "shell32.dll, 225"
    $Shortcut.Save()
}

Write-Host "SUCCESS: $AppName Installation Complete!" -ForegroundColor Green
Pause