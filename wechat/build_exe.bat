@echo off
echo Creating virtual environment...
python -m venv venv
call venv\Scripts\activate

echo Installing requirements...
pip install -r requirements.txt

echo Building executable...
pyinstaller wechat_bot.spec --noconfirm --clean

echo Build complete! Check dist/WeChatAutoLike folder.
echo You can copy the 'dist/WeChatAutoLike' folder to any location to run.
pause






