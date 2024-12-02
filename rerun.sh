echo "Загрузка последней версии backend'а из репозитория"
git pull
echo "Удаление старого контейнера"
docker rm -f api
echo "Удаление старого образа"
docker image rm -f api:latest
echo "Создание нового образа"
docker build -t api:latest .
echo "Запуск контейнера из нового образа"
docker run --name api -d -p 5000:5000 api:latest
echo "Deploy завершён"
