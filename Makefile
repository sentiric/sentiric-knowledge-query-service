.PHONY: help up down logs build clean setup

help:
	@echo "🎨 Sentiric AI Studio - Entegrasyon ve Test Laboratuvarı"
	@echo "-------------------------------------------------------"
	@echo "make setup   : .env dosyasını hazırlar ve sertifikaları kontrol eder"
	@echo "make up      : Tüm AI servislerini başlatır (Local Build)"
	@echo "make prod    : Hazır imajlardan başlatır (No Build)"
	@echo "make down    : Servisleri durdurur"
	@echo "make logs    : Logları izler"

setup:
	@if [ ! -f .env ]; then cp .env.example .env; echo "⚠️ .env oluşturuldu, lütfen düzenleyin!"; fi
	@if [ ! -d "../sentiric-certificates" ]; then echo "❌ '../sentiric-certificates' bulunamadı! Sertifika mount'u çalışmayacak."; exit 1; fi

# Geliştirme Modu: Override dosyasını kullanır (Local Build)
up: setup
	docker compose -f docker-compose.infra.yml -f docker-compose.yml -f docker-compose.override.yml up --build -d

# Üretim Simülasyonu: Override dosyasını YOK SAYAR (Hazır İmaj)
prod: setup
	docker compose -f docker-compose.infra.yml -f docker-compose.yml up -d

down:
	docker compose -f docker-compose.infra.yml -f docker-compose.yml -f docker-compose.override.yml down --remove-orphans

logs:
	docker compose -f docker-compose.infra.yml -f docker-compose.yml logs -f