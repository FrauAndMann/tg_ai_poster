# Деплой TG AI Poster на Oracle Cloud Free Tier

Oracle Cloud Free Tier предоставляет **бесплатные** ресурсы навсегда:
- До 4 ARM VM (Ampere A1) с суммарно 24GB RAM и 4 OCPU
- 200GB block storage
- 10TB/month outbound traffic

Для бота достаточно 1 VM.

---

## Шаг 1: Создание аккаунта Oracle Cloud

1. Перейди на https://www.oracle.com/cloud/free/
2. Нажми "Start for free"
3. Заполни данные (email, страна, имя, адрес)
4. **Важно**: потребуется кредитная карта для верификации (деньги не спишут)
5. Подтверди email и телефон

> Карта должна поддерживать 3D Secure. Иногда нужны попытки с разными картами.

---

## Шаг 2: Создание VM (Compute Instance)

1. В консоли Oracle Cloud открой **Compute > Instances**
2. Нажми **Create Instance**
3. Настрой:
   - **Name**: `tg-ai-poster`
   - **Compartment**: root (или создай новый)
4. В секции **Image and Shape**:
   - Нажми **Change Image**
   - Выбери **Canonical Ubuntu 22.04** (или Oracle Linux 8)
   - Нажми **Change Shape**
   - Выбери **VM.Standard.A1.Flex** (ARM)
   - Установи: **2 OCPU**, **6 GB RAM**
5. В секции **Primary VNIC**:
   - Оставь по умолчанию (создастся публичный IP)
6. В секции **Add SSH Keys**:
   - **ВАЖНО**: Выбери "Paste SSH keys" и вставь свой публичный ключ
   - Или скачай generated keys и сохрани приватный ключ
7. В секции **Boot Volume**:
   - Увеличь до **50 GB** (бесплатно до 200GB)
8. Нажми **Create**

> Если получаешь ошибку "Out of capacity" - попробуй другой регион или повтори позже.

---

## Шаг 3: Настройка Security List (Firewall)

Oracle Cloud имеет два уровня фаервола:

### 3.1 Security List (Oracle Console)

1. Перейди в **Networking > Virtual Cloud Networks**
2. Выбери свою VCN
3. Выбери **Security Lists** > **Default Security List**
4. Нажми **Add Ingress Rules**:
   ```
   Source CIDR: 0.0.0.0/0
   IP Protocol: TCP
   Source Port Range: All
   Destination Port Range: 22
   Description: SSH
   ```
   Добавь также порты 80 и 443 если нужны.

### 3.2 OS Firewall (на сервере)

```bash
sudo iptables -I INPUT -p tcp --dport 22 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
# Сохранить правила
sudo netfilter-persistent save 2>/dev/null || sudo iptables-save
```

---

## Шаг 4: Подключение к серверу

### Windows

1. Открой PowerShell
2. Подключись через SSH:
   ```powershell
   ssh -i путь\к\ключу.pem ubuntu@PUBLIC_IP
   ```
   Где:
   - `ключ.pem` - сохранённый приватный ключ
   - `PUBLIC_IP` - публичный IP инстанса (в консоли Oracle)

### Если ключ в PuTTY формате (.ppk)

1. Открой PuTTY
2. В **Session** введи: `ubuntu@PUBLIC_IP`
3. В **Connection > SSH > Auth > Credentials** укажи путь к .ppk файлу
4. Нажми **Open**

---

## Шаг 5: Установка Docker на сервере

После подключения к серверу выполни:

```bash
# Скачай и запусти скрипт настройки
curl -fsSL https://raw.githubusercontent.com/YOUR_REPO/main/deploy/setup-server.sh | bash

# Или вручную:
sudo apt-get update && sudo apt-get upgrade -y
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# Выйди и зайди снова для применения группы docker
```

---

## Шаг 6: Загрузка проекта на сервер

### Вариант A: Git Clone (рекомендуется)

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/tg_ai_poster.git
cd tg_ai_poster
```

### Вариант B: SCP (прямая загрузка)

На твоём локальном ПК:

```powershell
# Загрузить весь проект
scp -i ключ.pem -r D:\tg_ai_poster ubuntu@PUBLIC_IP:~/tg_ai_poster
```

### Вариант C: rsync (быстрее для повторных загрузок)

```powershell
# Установи rsync если нет (Windows: через WSL или cwRsync)
rsync -avz -e "ssh -i ключ.pem" /d/tg_ai_poster/ ubuntu@PUBLIC_IP:~/tg_ai_poster/
```

---

## Шаг 7: Настройка переменных окружения

На сервере создай `.env` файл:

```bash
cd ~/tg_ai_poster
nano .env
```

Вставь свои данные:

```env
# Telegram Bot
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHANNEL_ID=@your_channel

# Telethon (если используешь user mode)
TELETHON_API_ID=12345678
TELETHON_API_HASH=abcdef1234567890abcdef1234567890
TELETHON_PHONE=+79991234567

# LLM
OPENAI_API_KEY=sk-...
GLM_API_KEY=your_glm_key

# Admin
ADMIN_TELEGRAM_ID=123456789
```

Сохрани: `Ctrl+O`, Enter, `Ctrl+X`

---

## Шаг 8: Запуск контейнера

```bash
cd ~/tg_ai_poster

# Первый запуск (сборка образа)
docker-compose -f docker-compose.simple.yml up -d --build

# Проверь логи
docker logs -f tg-ai-poster

# Остановить
docker-compose -f docker-compose.simple.yml down

# Перезапустить
docker-compose -f docker-compose.simple.yml restart
```

---

## Шаг 9: Проверка работы

```bash
# Статус контейнера
docker ps

# Логи в реальном времени
docker logs -f tg-ai-poster

# Проверить что процесс работает
docker exec tg-ai-poster ps aux | grep python

# Запустить один раз для теста
docker exec tg-ai-poster python main.py --once --dry-run
```

---

## Полезные команды

| Команда | Описание |
|---------|----------|
| `docker logs -f tg-ai-poster` | Логи в реальном времени |
| `docker exec -it tg-ai-poster bash` | Войти в контейнер |
| `docker restart tg-ai-poster` | Перезапуск |
| `docker stats` | Использование ресурсов |
| `docker-compose logs` | Все логи compose |

---

## Автообновление (Watchtower)

Для автоматического обновления образа:

```bash
docker run -d \
  --name watchtower \
  -v /var/run/docker.sock:/var/run/docker.sock \
  containrrr/watchtower \
  --interval 86400 \
  tg-ai-poster
```

---

## Резервное копирование

### База данных

```bash
# Бэкап
docker exec tg-ai-poster python main.py --backup

# Скачать на локальный ПК
scp -i ключ.pem ubuntu@PUBLIC_IP:~/tg_ai_poster/data/backups/backup_*.tar.gz .
```

### Восстановление

```bash
# Загрузить бэкап на сервер
scp -i ключ.pem backup.tar.gz ubuntu@PUBLIC_IP:~/tg_ai_poster/

# Восстановить
docker exec tg-ai-poster python main.py --restore /app/backup.tar.gz
```

---

## Решение проблем

### "Out of capacity" при создании VM

Попробуй:
1. Другой регион (Frankfurt, Amsterdam, Phoenix)
2. Меньшие ресурсы (1 OCPU, 4GB RAM)
3. Повтори через несколько часов/дней

### Контейнер не стартует

```bash
docker logs tg-ai-poster
# Проверь .env файл
cat .env
# Проверь права доступа
ls -la data logs sessions
```

### Нет интернета в контейнере

```bash
# Проверь DNS
docker exec tg-ai-poster ping -c 3 google.com
```

### Ошибка "Too many open files"

```bash
# Увеличь лимиты на хосте
echo "* soft nofile 65535" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65535" | sudo tee -a /etc/security/limits.conf
```

---

## Альтернативы Oracle Cloud

| Платформа | Плюсы | Минусы |
|-----------|-------|--------|
| **Fly.io** | Простой деплой | $5/мес лимит |
| **Railway** | GitHub интеграция | Кредиты кончаются |
| **Google Cloud** | e2-micro бесплатно | 12 мес, карта нужна |
| **AWS** | 12 месяцев Free Tier | Сложнее настройка |
