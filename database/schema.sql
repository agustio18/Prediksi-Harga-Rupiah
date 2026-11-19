CREATE TABLE IF NOT EXISTS harga_harian (
    tanggal     DATE PRIMARY KEY,
    open        NUMERIC(14,4),
    high        NUMERIC(14,4),
    low         NUMERIC(14,4),
    close       NUMERIC(14,4) NOT NULL,
    sumber      VARCHAR(30) NOT NULL,
    diperbarui  TIMESTAMP DEFAULT NOW()
);

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
    file_model           VARCHAR(200),
    aktif                BOOLEAN DEFAULT FALSE
);

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
    id          SERIAL PRIMARY KEY,
    waktu       TIMESTAMP DEFAULT NOW(),
    sumber      VARCHAR(30),
    baris_baru  INTEGER,
    status      VARCHAR(10),
    pesan       TEXT
);
