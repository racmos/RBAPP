#!/usr/bin/env python3
"""
Script de diagnóstico para Riftbound Manager
Ejecutar: python3 diagnose.py
"""

import sys
import os

print("=" * 60)
print("DIAGNÓSTICO DE RIFTBOUND MANAGER")
print("=" * 60)

# 1. Verificar imports
print("\n1. Verificando imports...")
try:
    from flask import Flask
    print("   ✅ Flask importado correctamente")
except ImportError as e:
    print(f"   ❌ Error importando Flask: {e}")
    sys.exit(1)

try:
    from flask_sqlalchemy import SQLAlchemy
    print("   ✅ Flask-SQLAlchemy importado correctamente")
except ImportError as e:
    print(f"   ❌ Error importando Flask-SQLAlchemy: {e}")
    sys.exit(1)

try:
    from flask_login import LoginManager
    print("   ✅ Flask-Login importado correctamente")
except ImportError as e:
    print(f"   ❌ Error importando Flask-Login: {e}")
    sys.exit(1)

# 2. Verificar estructura de archivos
print("\n2. Verificando estructura de archivos...")
required_files = [
    'app/__init__.py',
    'app/models.py',
    'app/routes.py',
    'app/templates/base.html',
    'app/static/css/style.css',
    'config.py',
    'run.py',
    'requirements.txt'
]

for file in required_files:
    if os.path.exists(file):
        print(f"   ✅ {file}")
    else:
        print(f"   ❌ {file} - NO ENCONTRADO")

# 3. Verificar modelos
print("\n3. Verificando modelos...")
try:
    from app.models import User, RbSet, RbCard, RbCollection, RbDeck, RbCardMarket
    print("   ✅ User")
    print("   ✅ RbSet")
    print("   ✅ RbCard")
    print("   ✅ RbCollection")
    print("   ✅ RbDeck")
    print("   ✅ RbCardMarket")
except ImportError as e:
    print(f"   ❌ Error importando modelos: {e}")
    import traceback
    traceback.print_exc()

# 4. Verificar configuración
print("\n4. Verificando configuración...")
try:
    from config import Config
    print(f"   ✅ Config importado")
    if hasattr(Config, 'SQLALCHEMY_DATABASE_URI'):
        db_uri = Config.SQLALCHEMY_DATABASE_URI
        # Ocultar password
        if '@' in db_uri:
            parts = db_uri.split('@')
            safe_uri = parts[0].split(':')[0] + ':****@' + parts[1]
            print(f"   📊 DATABASE_URI: {safe_uri}")
        else:
            print(f"   📊 DATABASE_URI: {db_uri}")
    else:
        print("   ⚠️  SQLALCHEMY_DATABASE_URI no configurado")
except ImportError as e:
    print(f"   ❌ Error importando Config: {e}")

# 5. Verificar archivo .env
print("\n5. Verificando archivo .env...")
if os.path.exists('.env'):
    print("   ✅ Archivo .env existe")
    with open('.env', 'r') as f:
        lines = f.readlines()
        for line in lines:
            if line.strip() and not line.startswith('#'):
                key = line.split('=')[0]
                print(f"   📝 Variable: {key}")
else:
    print("   ⚠️  Archivo .env no encontrado")

# 6. Probar creación de app
print("\n6. Probando creación de aplicación...")
try:
    from app import create_app
    app = create_app()
    print("   ✅ Aplicación creada correctamente")
    print(f"   📊 Blueprints registrados: {list(app.blueprints.keys())}")
except Exception as e:
    print(f"   ❌ Error creando aplicación: {e}")
    import traceback
    traceback.print_exc()

# 7. Verificar conexión a base de datos
print("\n7. Verificando conexión a base de datos...")
try:
    from app import create_app, db
    app = create_app()
    with app.app_context():
        # Intentar una consulta simple
        result = db.session.execute(db.text("SELECT 1"))
        print("   ✅ Conexión a base de datos exitosa")
        
        # Verificar tablas
        result = db.session.execute(db.text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'riftbound'
            ORDER BY table_name
        """))
        tables = [row[0] for row in result]
        print(f"   📊 Tablas encontradas: {', '.join(tables)}")
        
        # Verificar tabla rbusers
        if 'rbusers' in tables:
            print("   ✅ Tabla rbusers existe")
        else:
            print("   ⚠️  Tabla rbusers NO existe (debería ser rbusers, no users)")
            
        # Verificar tabla rbcardmarket
        if 'rbcardmarket' in tables:
            print("   ✅ Tabla rbcardmarket existe")
        else:
            print("   ⚠️  Tabla rbcardmarket NO existe")
            
except Exception as e:
    print(f"   ❌ Error conectando a base de datos: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("DIAGNÓSTICO COMPLETADO")
print("=" * 60)
