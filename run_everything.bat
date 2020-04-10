docker start some-rabbit
docker start some-postgres
timeout /t 30
start cmd.exe /k "cd services && C:\mstag-python\scripts\activate && python logviewer.py"
start cmd.exe /k "cd auth_gateway && C:\mstag-python\scripts\activate && python manage.py runserver 0.0.0.0:8000"
start cmd.exe /k "cd services\profile && C:\mstag-python\scripts\activate && python profile_service.py"
start cmd.exe /k "cd services\notifications && C:\mstag-python\scripts\activate && python notifications_service.py"
start cmd.exe /k "cd services\auth && C:\mstag-python\scripts\activate && python auth_service.py"
start cmd.exe /k "cd services\presence && C:\mstag-python\scripts\activate && python presence_service.py"
start cmd.exe /k "cd services\chat && C:\mstag-python\scripts\activate && python chat_service.py"
start cmd.exe /k "cd services\teams && C:\mstag-python\scripts\activate && python team_service.py"
start cmd.exe /k "cd services\game && C:\mstag-python\scripts\activate && python game_service_2.py"