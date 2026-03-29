-- ============================================
-- S3M NAC System — PostgreSQL Init Script
-- FreeRADIUS standart sema + seed data
-- ============================================

-- ============================================
-- 1. TABLOLAR
-- ============================================

-- Kullanici kimlik bilgileri (username/password)
CREATE TABLE IF NOT EXISTS radcheck (
    id          SERIAL PRIMARY KEY,
    username    VARCHAR(64) NOT NULL DEFAULT '',
    attribute   VARCHAR(64) NOT NULL DEFAULT '',
    op          CHAR(2) NOT NULL DEFAULT ':=',
    value       VARCHAR(253) NOT NULL DEFAULT ''
);
CREATE INDEX idx_radcheck_username ON radcheck(username);

-- Kullaniciya donulecek RADIUS attribute'lari
CREATE TABLE IF NOT EXISTS radreply (
    id          SERIAL PRIMARY KEY,
    username    VARCHAR(64) NOT NULL DEFAULT '',
    attribute   VARCHAR(64) NOT NULL DEFAULT '',
    op          CHAR(2) NOT NULL DEFAULT ':=',
    value       VARCHAR(253) NOT NULL DEFAULT ''
);
CREATE INDEX idx_radreply_username ON radreply(username);

-- Kullanici-grup iliskileri
CREATE TABLE IF NOT EXISTS radusergroup (
    id          SERIAL PRIMARY KEY,
    username    VARCHAR(64) NOT NULL DEFAULT '',
    groupname   VARCHAR(64) NOT NULL DEFAULT '',
    priority    INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX idx_radusergroup_username ON radusergroup(username);

-- Grup bazli attribute'lar (VLAN atamalari vs.)
CREATE TABLE IF NOT EXISTS radgroupreply (
    id          SERIAL PRIMARY KEY,
    groupname   VARCHAR(64) NOT NULL DEFAULT '',
    attribute   VARCHAR(64) NOT NULL DEFAULT '',
    op          CHAR(2) NOT NULL DEFAULT ':=',
    value       VARCHAR(253) NOT NULL DEFAULT ''
);
CREATE INDEX idx_radgroupreply_groupname ON radgroupreply(groupname);

-- Accounting kayitlari (oturum verileri)
CREATE TABLE IF NOT EXISTS radacct (
    radacctid           BIGSERIAL PRIMARY KEY,
    acctsessionid       VARCHAR(64) NOT NULL DEFAULT '',
    acctuniqueid        VARCHAR(32) NOT NULL DEFAULT '',
    username            VARCHAR(64) NOT NULL DEFAULT '',
    realm               VARCHAR(64) DEFAULT '',
    nasipaddress        VARCHAR(15) NOT NULL DEFAULT '',
    nasportid           VARCHAR(32) DEFAULT NULL,
    nasporttype         VARCHAR(32) DEFAULT NULL,
    acctstarttime       TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    acctupdatetime      TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    acctstoptime        TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    acctinterval        INTEGER DEFAULT NULL,
    acctsessiontime     INTEGER DEFAULT NULL,
    acctauthentic       VARCHAR(32) DEFAULT NULL,
    connectinfo_start   VARCHAR(128) DEFAULT NULL,
    connectinfo_stop    VARCHAR(128) DEFAULT NULL,
    acctinputoctets     BIGINT DEFAULT NULL,
    acctoutputoctets    BIGINT DEFAULT NULL,
    calledstationid     VARCHAR(50) NOT NULL DEFAULT '',
    callingstationid    VARCHAR(50) NOT NULL DEFAULT '',
    acctterminatecause  VARCHAR(32) NOT NULL DEFAULT '',
    servicetype         VARCHAR(32) DEFAULT NULL,
    framedprotocol      VARCHAR(32) DEFAULT NULL,
    framedipaddress     VARCHAR(15) NOT NULL DEFAULT '',
    framedipv6address   VARCHAR(45) NOT NULL DEFAULT '',
    framedipv6prefix    VARCHAR(45) NOT NULL DEFAULT '',
    framedinterfaceid   VARCHAR(44) NOT NULL DEFAULT '',
    delegatedipv6prefix VARCHAR(45) NOT NULL DEFAULT ''
);
CREATE INDEX idx_radacct_username ON radacct(username);
CREATE INDEX idx_radacct_acctsessionid ON radacct(acctsessionid);
CREATE INDEX idx_radacct_acctsessiontime ON radacct(acctsessiontime);
CREATE INDEX idx_radacct_acctstarttime ON radacct(acctstarttime);
CREATE INDEX idx_radacct_acctuniqueid ON radacct(acctuniqueid);
CREATE UNIQUE INDEX idx_radacct_acctuniqueid_unique ON radacct(acctuniqueid);

-- NAS (Network Access Server) client tanimlari
CREATE TABLE IF NOT EXISTS nas (
    id          SERIAL PRIMARY KEY,
    nasname     VARCHAR(128) NOT NULL,
    shortname   VARCHAR(32),
    type        VARCHAR(30) DEFAULT 'other',
    ports       INTEGER DEFAULT NULL,
    secret      VARCHAR(60) NOT NULL DEFAULT 'testing123',
    server      VARCHAR(64) DEFAULT NULL,
    community   VARCHAR(50) DEFAULT NULL,
    description VARCHAR(200) DEFAULT 'RADIUS Client'
);
CREATE INDEX idx_nas_nasname ON nas(nasname);

-- ============================================
-- 2. SEED DATA
-- ============================================

-- ============================================
-- KULLANICI SIFRELERI
-- SSHA-Password (Salted SHA-1) kullaniyoruz.
-- Format: base64( SHA1(password + salt) + salt )
-- FreeRADIUS PAP modulu SSHA formatini native
-- olarak destekler ve otomatik cozumler.
-- ============================================

-- Admin kullanicisi (sifre: Admin123!)
INSERT INTO radcheck (username, attribute, op, value)
VALUES ('testadmin', 'SSHA-Password', ':=', 'HNu0+X99zQrvDHK1ZFrWRAxTmNgNf2+g');

-- Employee kullanicisi (sifre: User123!)
INSERT INTO radcheck (username, attribute, op, value)
VALUES ('testuser', 'SSHA-Password', ':=', 'yYKzZwlECBwWuUH/INu4ziMd6w6SVj+d');

-- Guest kullanicisi (sifre: Guest123!)
INSERT INTO radcheck (username, attribute, op, value)
VALUES ('testguest', 'SSHA-Password', ':=', 'fir43gDYSJBLoCBLyq0+jBNCIOXIY2Q7');

-- MAC adresi tabanli cihaz (MAB icin)
-- MAB'de MAC adresi hem username hem password olarak gelir.
-- Cleartext kalir cunku cihaz hash gondeREMEZ.
INSERT INTO radcheck (username, attribute, op, value)
VALUES ('AA:BB:CC:DD:EE:FF', 'Cleartext-Password', ':=', 'AA:BB:CC:DD:EE:FF');

-- ============================================
-- KULLANICI-GRUP ILISKILERI
-- ============================================
INSERT INTO radusergroup (username, groupname, priority) VALUES ('testadmin', 'admin', 1);
INSERT INTO radusergroup (username, groupname, priority) VALUES ('testuser', 'employee', 1);
INSERT INTO radusergroup (username, groupname, priority) VALUES ('testguest', 'guest', 1);
INSERT INTO radusergroup (username, groupname, priority) VALUES ('AA:BB:CC:DD:EE:FF', 'guest', 1);

-- ============================================
-- GRUP BAZLI VLAN ATAMALARI
-- Tunnel-Type = VLAN (13)
-- Tunnel-Medium-Type = IEEE-802 (6)
-- Tunnel-Private-Group-Id = VLAN numarasi
-- ============================================

-- Admin grubu -> VLAN 10
INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES ('admin', 'Tunnel-Type', ':=', 'VLAN');
INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES ('admin', 'Tunnel-Medium-Type', ':=', 'IEEE-802');
INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES ('admin', 'Tunnel-Private-Group-Id', ':=', '10');

-- Employee grubu -> VLAN 20
INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES ('employee', 'Tunnel-Type', ':=', 'VLAN');
INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES ('employee', 'Tunnel-Medium-Type', ':=', 'IEEE-802');
INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES ('employee', 'Tunnel-Private-Group-Id', ':=', '20');

-- Guest grubu -> VLAN 30
INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES ('guest', 'Tunnel-Type', ':=', 'VLAN');
INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES ('guest', 'Tunnel-Medium-Type', ':=', 'IEEE-802');
INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES ('guest', 'Tunnel-Private-Group-Id', ':=', '30');
