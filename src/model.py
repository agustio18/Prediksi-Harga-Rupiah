
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

from src.features import siapkan_dataset


def buat_model_svr():
    """
    Membuat pipeline StandardScaler dan SVR kernel RBF.
    """

    model = Pipeline([
        ("scaler", StandardScaler()),
        ("svr", SVR(kernel="rbf")),
    ])

    return model


def latih_model(dataset):
    """
    Melatih SVR menggunakan seluruh data berlabel.
    """

    paket = siapkan_dataset(dataset)

    model = buat_model_svr()

    model.fit(
        paket["X_train"],
        paket["y_train"]
    )

    return model, paket


def prediksi_return(model, X_prediksi):
    """
    Memprediksi return untuk minggu berikutnya.
    """

    hasil = model.predict(X_prediksi)

    return float(hasil[0])


def konversi_ke_harga(return_prediksi, harga_acuan):
    """
    Mengubah prediksi return menjadi prediksi harga kurs.
    """

    harga_prediksi = harga_acuan * (
        1 + return_prediksi / 100
    )

    return float(harga_prediksi)
