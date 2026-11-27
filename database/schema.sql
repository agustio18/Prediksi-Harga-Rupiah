CREATE TABLE IF NOT EXISTS harga_harian (
    tanggal     DATE PRIMARY KEY,
    open        NUMERIC(15,4),
    high        NUMERIC(15,4),
    low         NUMERIC(15,4),
    close       NUMERIC(15,4) NOT NULL,
    sumber      VARCHAR(30) NOT NULL,
    status      VARCHAR(10) NOT NULL DEFAULT 'VALID',
    diperbarui  TIMESTAMP DEFAULT NOW()
);

ALTER TABLE harga_harian
ADD COLUMN IF NOT EXISTS status VARCHAR(10) NOT NULL DEFAULT 'VALID';



CREATE TABLE IF NOT EXISTS model_versi (
    id                   SERIAL PRIMARY KEY,
    nama                 VARCHAR(60),
    dibuat_pada          TIMESTAMP,
    fitur                TEXT,
    kernel               VARCHAR(10),
    c                    NUMERIC,
    epsilon              NUMERIC,
    gamma                VARCHAR(20),
    tanggal_data_awal    DATE,
    tanggal_data_akhir   DATE,
    mae_persen           NUMERIC,
    rmse_persen          NUMERIC,
    akurasi_arah         NUMERIC,
    mae_baseline_persen  NUMERIC,
    tanggal_uji_awal     DATE,
    tanggal_uji_akhir    DATE,
    file_model           VARCHAR(200),
    aktif                BOOLEAN DEFAULT FALSE
);

ALTER TABLE model_versi
ADD COLUMN IF NOT EXISTS tanggal_uji_awal DATE;

ALTER TABLE model_versi
ADD COLUMN IF NOT EXISTS tanggal_uji_akhir DATE;


CREATE TABLE IF NOT EXISTS prediksi (
    id             SERIAL PRIMARY KEY,
    tanggal_acuan  DATE,
    tanggal_target DATE,
    harga_acuan    NUMERIC(14,4),
    return_persen  NUMERIC(10,6),
    harga_prediksi NUMERIC(14,4),
    model_id       INTEGER REFERENCES model_versi(id),
    dibuat_pada    TIMESTAMP DEFAULT NOW(),
    harga_aktual   NUMERIC(14,4),
    selisih        NUMERIC(14,4),
    galat_persen   NUMERIC(10,6),
    arah_benar     BOOLEAN,
    CONSTRAINT prediksi_unik UNIQUE (tanggal_acuan, model_id)
);


CREATE TABLE IF NOT EXISTS log_update (
    id              SERIAL PRIMARY KEY,
    waktu           TIMESTAMP DEFAULT NOW(),
    sumber          VARCHAR(30),
    baris_diproses  INTEGER,
    status          VARCHAR(10),
    pesan           TEXT
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'log_update'
          AND column_name = 'baris_baru'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'log_update'
          AND column_name = 'baris_diproses'
    ) THEN
        ALTER TABLE log_update RENAME COLUMN baris_baru TO baris_diproses;
    END IF;
END
$$;


CREATE UNIQUE INDEX IF NOT EXISTS
    uq_model_versi_satu_aktif
ON model_versi (aktif)
WHERE aktif = TRUE;