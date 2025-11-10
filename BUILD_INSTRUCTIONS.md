# Building Windows Executable - Instructions

## Quick Start

### Option 1: Using the Build Script (Easiest)

1. Simply double-click `build_exe.bat` or run it from command line:
   ```cmd
   build_exe.bat
   ```

2. The script will:
   - Install PyInstaller if needed
   - Clean previous builds
   - Build the executable
   - Move it to the project root

3. You'll get `QuestradeTrading.exe` in your project folder

### Option 2: Manual Build

1. Install PyInstaller:
   ```cmd
   pip install pyinstaller
   ```

2. Build using the spec file:
   ```cmd
   pyinstaller --clean questrade_trading.spec
   ```

3. The executable will be in `dist\QuestradeTrading.exe`

## Running the Executable

### First Time Setup

1. Create a folder for your trading system (e.g., `C:\Trading\`)

2. Copy these files to the folder:
   - `QuestradeTrading.exe` (the executable)
   - `.env` (your Questrade credentials)
   - `watchlist.txt` (your ticker list)
   - `watchlist.txt.example` (optional, for reference)

3. Double-click `QuestradeTrading.exe` to run

**Note:** The launcher will automatically check for .env and watchlist.txt files and create sample versions if they don't exist.

### Required Files

The executable needs these files in the **same folder**:

#### .env (REQUIRED)
```
QUESTRADE_REFRESH_TOKEN=your_refresh_token_here
```

Get your refresh token from: https://login.questrade.com/APIAccess/

#### watchlist.txt (REQUIRED)
```
# Your watchlist
QQQ
SPY
AAPL
```

See `watchlist.txt.example` for more examples.

## Features of the Executable

The launcher provides a menu-driven interface:

1. **Strategy Selector** - Analyze watchlist for opportunities
2. **Trade Generator** - Generate detailed trade recommendations
3. **Position Tracker** - View current positions and P&L
4. **Trade Executor** - Execute trades from recommendations
5. **Cleanup Utilities** - Clean temp files
6. **Run Tests** - Execute unit test suite

## Output Files

The executable will create these files:

- `trade_recommendations.csv` - Trade setups
- `portfolio_*.csv` - Portfolio snapshots
- `execution_log_*.csv` - Trade execution logs
- `strategy_debug.log` - Debug logs
- `temp-*.json` - Temporary API response files

## Advanced Configuration

### Customizing the Build

Edit `questrade_trading.spec` to:

- **Add an icon**: Set `icon='path/to/icon.ico'` in the EXE section
- **Change executable name**: Modify `name='QuestradeTrading'`
- **Include additional data files**: Add to `datas=[]` list
- **Reduce file size**: Set `upx=False` if having issues

### Build Options

**One-file executable** (slower startup, easier to distribute):
```cmd
pyinstaller --onefile --clean main.py
```

**One-folder executable** (faster startup, multiple files):
```cmd
pyinstaller --onedir --clean main.py
```

**With custom icon**:
```cmd
pyinstaller --onefile --icon=icon.ico --clean main.py
```

## Troubleshooting

### "Module not found" errors

If you get import errors, add the missing module to `hiddenimports` in `questrade_trading.spec`:

```python
hiddenimports=[
    'requests',
    'your_missing_module',  # Add here
],
```

### Executable won't run

1. Check that `.env` file is in the same folder
2. Check that your refresh token is valid
3. Run from command line to see error messages:
   ```cmd
   QuestradeTrading.exe
   ```

### "Access token expired" errors

Your refresh token needs to be regenerated. Get a new one from:
https://login.questrade.com/APIAccess/

### Antivirus blocking the executable

PyInstaller executables sometimes trigger antivirus warnings. This is a false positive. You can:
- Add an exception in your antivirus
- Run from a trusted folder
- Code-sign the executable (advanced)

## Distribution

To share with others, create a ZIP file with:

```
QuestradeTrading/
├── QuestradeTrading.exe
├── watchlist.txt.example
└── README.txt (instructions for users)
```

**DO NOT include** your `.env` file with credentials!

Users will need to:
1. Extract the ZIP
2. Create their own `.env` file
3. Create their own `watchlist.txt`
4. Run `QuestradeTrading.exe`

## Building for Different Python Versions

The executable includes the Python version you built it with. To build for a specific version:

1. Install that Python version
2. Create a virtual environment:
   ```cmd
   py -3.11 -m venv .venv311
   .venv311\Scripts\activate
   ```
3. Install dependencies:
   ```cmd
   pip install -r requirements.txt
   pip install pyinstaller
   ```
4. Build:
   ```cmd
   pyinstaller --clean questrade_trading.spec
   ```

## File Size Optimization

The executable is typically 20-50 MB. To reduce size:

1. **Use UPX compression** (already enabled in spec file)
2. **Exclude unnecessary modules** in spec file:
   ```python
   excludes=['tkinter', 'matplotlib', 'pandas'],  # If not needed
   ```
3. **Use --onefile** instead of --onedir

## Testing the Executable

Before distributing:

1. Test in a clean folder (not the development folder)
2. Test on another Windows machine if possible
3. Test with a fresh `.env` file
4. Test all menu options (1-6)
5. Verify output files are created correctly

## Getting Help

If you encounter issues:

1. Check the console output for error messages
2. Check `strategy_debug.log` for detailed logs
3. Run the Python script directly to compare behavior:
   ```cmd
   python main.py
   ```
4. Check PyInstaller logs in the `build/` folder
