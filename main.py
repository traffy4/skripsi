import os
import pandas as pd
import mysql.connector as sql
import numpy as np

from flask import Flask, render_template, request, redirect, url_for, session
from surprise import Dataset, Reader, KNNBasic, accuracy
from surprise.model_selection import train_test_split

application = Flask(__name__)
# Konfigurasi db mysql
application.config['DB_USER'] = 'root'
application.config['DB_PASSWORD'] = ''
application.config['DB_NAME'] = 'rekomendasi'
application.config['DB_HOST'] = 'localhost'

# Konfigurasi secret key
application.secret_key = 'abc'

conn = cursor = None


# Inisialisasi db
def openDb():
    global conn, cursor
    conn = sql.connect(
        user=application.config['DB_USER'],
        password=application.config['DB_PASSWORD'],
        database=application.config['DB_NAME'],
        host=application.config['DB_HOST'],
    )
    cursor = conn.cursor()


# Menutup db
def closeDb():
    global conn, cursor
    cursor.close()
    conn.close()


@application.route('/login', methods=['GET', 'POST'])
def login():
    openDb()
    if "username" in session:
        menu = []

        cursor.execute("SELECT * FROM menu")
        for id_menu, nama_menu, gambar_menu, deskripsi_menu, short_deskripsi_menu in cursor.fetchall():
            menu.append((id_menu, nama_menu, gambar_menu, deskripsi_menu, short_deskripsi_menu))

        closeDb()
        return render_template('index.html')
    else:
        if request.method == 'POST':
            username = request.form['username']

            menu = []

            cursor.execute("SELECT * FROM menu")
            for id_menu, nama_menu, gambar_menu, deskripsi_menu, short_deskripsi_menu in cursor.fetchall():
                menu.append((id_menu, nama_menu, gambar_menu, deskripsi_menu, short_deskripsi_menu))

            # Fungsi mengambil semua data dari tabel user apabila username ada
            cursor.execute('''
                        SELECT * FROM user where username='%s'
                    ''' % (username))
            rows = cursor.fetchall()

            # Jika variabel rows bernilai 1
            if len(rows) == 1:
                # Session diset permanent sampai di clear cache untuk login site di browser dihapus
                session.permanent = True
                # Memasukkan email dan password ke dalam sesi
                session['username'] = username
                closeDb()
                return redirect(url_for('index'))
            else:
                # Fungsi untuk memasukkan data ke tabel menu
                cursor.execute('''
                            INSERT INTO user (id_user, username) VALUES ('%s','%s') 
                        ''' % ('NULL', username))
                conn.commit()

                closeDb()
                return redirect(url_for('index'))

    closeDb()
    return render_template('login.html')


@application.route('/', methods=['GET', 'POST'])
def index():
    if "username" not in session:
        return redirect(url_for('login'))

    else:
        openDb()
        menu = []

        cursor.execute("SELECT * FROM menu")
        for id_menu, nama_menu, gambar_menu, deskripsi_menu, short_deskripsi_menu in cursor.fetchall():
            menu.append((id_menu, nama_menu, gambar_menu, deskripsi_menu, short_deskripsi_menu))
        closeDb()
        return render_template('index.html', menu=menu)


@application.route('/rekomendasi', methods=['GET', 'POST'])
def rekomendasi():
    openDb()

    cursor.execute("SELECT id_user FROM user WHERE username='%s'" % session['username'])
    user_id = cursor.fetchone()

    cursor.execute('''
                SELECT * FROM rating where id_user='%s'
            ''' % (user_id))
    rows = cursor.fetchall()

    if len(rows) == 0:
        return render_template('rekomendasi.html')
    else:
        # Membaca tabel database
        ratings = pd.read_sql('SELECT * FROM rating', con=conn)
        menus = pd.read_sql('SELECT * FROM menu', con=conn)

        # Menampilkan info kolom dan baris dari ratings
        print(ratings)

        # Menampilkan info kolom dan baris dari menus
        print(menus)

        # Memanggil data dari dataframe
        data = Dataset.load_from_df(ratings, Reader())

        # Generate data train
        trainset = data.build_full_trainset()

        # Algoritma KNN dengan algoritma pearson correlation
        sim_options = {'name': 'pearson'}
        model = KNNBasic(sim_options=sim_options)
        model.fit(trainset)

        # Menampilkan semua id menu
        all_menu = menus.id_menu.unique()
        print(all_menu)

        # Menampilkan semua id menu yang sudah dirating
        rated = ratings[ratings.id_user == user_id].id_menu
        print(rated)

        # Menampilkan semua id menu yang belum dirating
        not_rated = np.setdiff1d(all_menu, rated)
        print(not_rated)

        # Menghitung prediksi rating
        score = [model.predict(user_id[0], id_menu) for id_menu in not_rated]
        print(score)

        # Mengurutkan prediksi rating
        est = [model.predict(user_id[0], id_menu).est for id_menu in not_rated]
        sort = pd.DataFrame({'id_menu': not_rated, 'est': est}).sort_values('est', ascending=False)
        print(sort)

        menu = []
        for i in sort.itertuples():
            cursor.execute("SELECT * FROM menu WHERE id_menu='%s'" % i.id_menu)
            for id_menu, nama_menu, gambar_menu, deskripsi_menu, short_deskripsi_menu in cursor.fetchall():
                menu.append((id_menu, nama_menu, gambar_menu, deskripsi_menu, short_deskripsi_menu))

        # Menghitung akurasi MAE
        train_set, test_set = train_test_split(data, test_size=.25, shuffle=False)

        # Train algoritma pada train_set, dan prediksi rating untuk test_set
        model.fit(train_set)
        predictions = model.test(test_set)

        # Menghitung MAE
        accuracy.mae(predictions)

        closeDb()
        return render_template('rekomendasi.html', menu=menu)


@application.route('/detail/<id>', methods=['GET', 'POST'])
def detail(id):
    openDb()
    cursor.execute("SELECT id_user FROM user WHERE username='%s'" % session['username'])
    id_user = cursor.fetchone()

    cursor.execute("SELECT rating FROM rating WHERE id_menu='%s' AND id_user='%s'" % (id, id_user[0]))
    rating = cursor.fetchone()

    if request.method == 'POST':

        update_rating = request.form['rating']

        if rating == None:

            cursor.execute(
                "INSERT INTO rating (id_user, id_menu, rating) VALUES ('%s', '%s', '%s')" % (
                    id_user[0], id, update_rating))
            conn.commit()

        else:
            cursor.execute(
                "UPDATE rating SET rating='%s' WHERE id_menu='%s' AND id_user='%s'" % (update_rating, id, id_user[0]))
            conn.commit()

    cursor.execute("SELECT * FROM menu WHERE id_menu='%s'" % id)
    menu = cursor.fetchone()

    closeDb()
    return render_template('detail.html', menu=menu, rating=rating)


if __name__ == '__main__':
    application.run(host="localhost", port=5000, debug=True)
