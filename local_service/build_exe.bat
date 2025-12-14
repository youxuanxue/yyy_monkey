@echo off
echo Creating virtual environment...
python -m venv venv
call venv\Scripts\activate

echo Installing requirements...
pip install -r requirements.txt

echo Building executable...
pyinstaller douyin_bot.spec --noconfirm --clean

echo Build complete! Check dist/DouyinAutoLike folder.
echo You can copy the 'dist/DouyinAutoLike' folder to any location to run.
pause

