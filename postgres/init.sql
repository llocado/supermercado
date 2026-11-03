-- Una sola instancia de Postgres con una base y un usuario por servicio (en desarrollo son cuatro contenedores).
-- Credenciales de DEMO: la base no se publica fuera de la red interna de Docker.
CREATE USER foodstore_user WITH PASSWORD 'foodstore_password';
CREATE DATABASE foodstore_db OWNER foodstore_user;
CREATE USER carrito_user WITH PASSWORD 'carrito_password';
CREATE DATABASE carrito_db OWNER carrito_user;
CREATE USER pedidos_user WITH PASSWORD 'pedidos_password';
CREATE DATABASE pedidos_db OWNER pedidos_user;
CREATE USER pagos_user WITH PASSWORD 'pagos_password';
CREATE DATABASE pagos_db OWNER pagos_user;
