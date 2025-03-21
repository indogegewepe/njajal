from sqlalchemy.orm import Session
from sqlalchemy import select
from database import get_db
from models import Dosen, DataDosen, MkGenap, Hari, Jam, Ruang, PreferensiDosen

import copy
import numpy as np
import pandas as pd
from datetime import datetime
from collections import defaultdict
import json
import random

def query_to_dataframe(query_result):
    dict_list = [item.__dict__ for item in query_result]
    # Hapus atribut internal SQLAlchemy
    for d in dict_list:
        d.pop("_sa_instance_state", None)
    return pd.DataFrame(dict_list)

# Mendapatkan session secara langsung (pastikan untuk menutup session setelah selesai)
db: Session = next(get_db())

# Mengambil data dari database
dosen_records = db.query(Dosen).all()
mk_genap_records = db.query(MkGenap).all()
data_dosen_records = db.query(DataDosen).all()
hari_records = db.query(Hari).all()
ruang_records = db.query(Ruang).all()
jam_records = db.query(Jam).all()

# Mengonversi query result menjadi DataFrame
dosen_df = query_to_dataframe(dosen_records)
mk_genap_df = query_to_dataframe(mk_genap_records)
data_dosen_df = query_to_dataframe(data_dosen_records)
hari_df = query_to_dataframe(hari_records)
ruang_df = query_to_dataframe(ruang_records)
jam_df = query_to_dataframe(jam_records)

# Fungsi konversi waktu ke menit
def time_to_minutes(t):
    try:
        dt = datetime.strptime(t, "%H:%M:%S")
    except ValueError:
        dt = datetime.strptime(t, "%H:%M")
    return dt.hour * 60 + dt.minute

# Urutkan jam_df sebelum generate slot
jam_df = jam_df.sort_values('id_jam')

# Gabungkan data menggunakan merge
merged_df = pd.merge(
    pd.merge(data_dosen_df, dosen_df, on='id_dosen'),
    mk_genap_df, on='id_mk_genap'
)

# Tambahkan temporary id secara unik untuk setiap baris di merged_df
merged_df['temp_id'] = range(1, len(merged_df) + 1)

def slot_generator():
    slots = []
    id_counter = 1
    for hari in hari_df['nama_hari']:
        for ruang in ruang_df['nama_ruang']:
            for jam in jam_df.itertuples():
                slots.append({
                    "id_slot": id_counter,
                    "id_mk": None,
                    "mata_kuliah": None,
                    "id_dosen": None,
                    "dosen": None,
                    "ruang": ruang,
                    "hari": hari,
                    "jam_mulai": jam.jam_awal,
                    "jam_selesai": jam.jam_akhir,
                    "semester": None,
                    "kelas": None,
                    "sks": None,
                    "metode": None,
                    "status": None,
                    "temp_id": None
                })
                id_counter += 1
    return slots

def create_random_schedule():
    schedule = slot_generator()
    merged_shuffled = merged_df.iterrows()
    
    # Tracking alokasi (untuk referensi)
    room_allocations = defaultdict(list)
    teacher_allocations = defaultdict(list)
    class_allocations = defaultdict(list)
    
    for _, row in merged_shuffled:
        id_mk = row['id_mk_genap']
        mata_kuliah = row['nama_mk_genap']
        id_dosen = row['id_dosen']
        dosen = row['nama_dosen']
        kelas = row['kelas']
        sks = int(row['sks'])
        semester = row['smt']
        metode = row['metode']
        temp_id = row['temp_id']
        
        possible_positions = list(range(len(schedule) - sks + 1))
        random.shuffle(possible_positions)
        
        candidate_blocks = []
        for i in possible_positions:
            block = schedule[i:i+sks]
            if not all(slot['mata_kuliah'] is None for slot in block) or not all(slot['hari'] == block[0]['hari'] for slot in block):
                continue
            if not all(slot['ruang'] == block[0]['ruang'] for slot in block):
                continue
            hari = block[0]['hari']
            ruang = block[0]['ruang']
            time_block = (time_to_minutes(block[0]['jam_mulai']), time_to_minutes(block[-1]['jam_selesai']))
            kelas_already = len(class_allocations[(kelas, hari)]) > 0
            candidate_blocks.append((block, time_block, kelas_already))
        
        if candidate_blocks:
            selected_block = candidate_blocks[0][0]
            for slot in selected_block:
                slot.update({
                    "id_mk": id_mk,
                    "mata_kuliah": mata_kuliah,
                    "id_dosen": id_dosen,
                    "dosen": dosen,
                    "kelas": kelas,
                    "sks": sks,
                    "semester": semester,
                    "metode": metode,
                    "temp_id": temp_id
                })
            hari = selected_block[0]['hari']
            ruang = selected_block[0]['ruang']
            time_block = (time_to_minutes(selected_block[0]['jam_mulai']),
                          time_to_minutes(selected_block[-1]['jam_selesai']))
            room_allocations[(ruang, hari)].append(time_block)
            teacher_allocations[(dosen, hari)].append(time_block)
            class_allocations[(kelas, hari)].append(time_block)
        else:
            print(f"Gagal menempatkan: {kelas} - {mata_kuliah} - {dosen}")
    
    return schedule

# Fungsi untuk mengambil konfigurasi preferensi dosen
def get_lecturer_preferences(db: Session):
    # Melakukan query join antara tabel Dosen dan PreferensiDosen
    query = (
        select(
            Dosen.nama_dosen,
            PreferensiDosen.hari,
            PreferensiDosen.jam_mulai_id,
            PreferensiDosen.jam_selesai_id,
            PreferensiDosen.id_preferensi
        )
        .join(PreferensiDosen, Dosen.id_dosen == PreferensiDosen.dosen_id)
    )
    results = db.execute(query).fetchall()
    
    # Membuat dictionary untuk mengelompokkan preferensi berdasarkan nama dosen
    preferences = {}
    for row in results:
        nama_dosen = row[0]
        pref = {
            'hari': row[1],
            'jam_mulai_id': row[2],
            'jam_selesai_id': row[3],
            'id_preferensi': row[4]
        }
        # Jika dosen sudah ada dalam dictionary, tambahkan preferensi ke list-nya
        if nama_dosen in preferences:
            preferences[nama_dosen].append(pref)
        else:
            preferences[nama_dosen] = [pref]
    
    return preferences

print(get_lecturer_preferences(db))

# def collect_conflicts(schedule):
#     conflict_temp_ids = set()
#     lecturer_preferences = get_lecturer_preferences(db)
#     preference_conflict_temp_ids = set()
    
#     # --- (A) Konsistensi Ruangan dalam satu temp_id ---
#     temp_groups = defaultdict(list)
#     for slot in schedule:
#         if slot['mata_kuliah'] is not None and slot.get('temp_id') is not None:
#             temp_groups[slot['temp_id']].append(slot)
#     room_consistency_conflicts = []
#     for tid, slots in temp_groups.items():
#         ruangan_set = {slot['ruang'] for slot in slots}
#         if len(ruangan_set) > 1:
#             conflict_temp_ids.add(tid)
#             room_consistency_conflicts.append({
#                 'temp_id': tid,
#                 'ruangan': list(ruangan_set),
#                 'slot_ids': [slot['id_slot'] for slot in slots]
#             })
    
#     # --- (B) Konflik Dosen: Dosen tidak boleh mengajar 2 course berbeda pada jam/hari yang sama ---
#     teacher_conflicts = []
#     teacher_groups = defaultdict(list)
#     for slot in schedule:
#         if slot['mata_kuliah'] is None:
#             continue
#         key = (slot['dosen'], slot['hari'].lower())
#         teacher_groups[key].append(slot)

#     # Iterasi untuk setiap grup (dosen, hari)
#     for key, slots in teacher_groups.items():
#         # Urutkan slot berdasarkan jam_mulai
#         slots.sort(key=lambda s: time_to_minutes(s['jam_mulai']))
#         for i in range(len(slots)):
#             for j in range(i + 1, len(slots)):
#                 start_i = time_to_minutes(slots[i]['jam_mulai'])
#                 end_i   = time_to_minutes(slots[i]['jam_selesai'])
#                 start_j = time_to_minutes(slots[j]['jam_mulai'])
#                 # Jika slot kedua mulai sebelum slot pertama selesai, artinya ada tumpang tindih
#                 if start_j < end_i:
#                     # Jika mata kuliah berbeda, maka terjadi konflik
#                     if slots[i]['mata_kuliah'] != slots[j]['mata_kuliah']:
#                         tid_i = slots[i].get('temp_id')
#                         tid_j = slots[j].get('temp_id')
#                         if tid_i is not None:
#                             conflict_temp_ids.add(tid_i)
#                         if tid_j is not None:
#                             conflict_temp_ids.add(tid_j)
#                         teacher_conflicts.append((slots[i]['id_slot'], slots[j]['id_slot']))

#     # --- (C) Konflik Ruangan: Ruang yang sama tidak boleh digunakan untuk 2 kelas berbeda pada jam/hari yang sama ---
#     room_conflicts = []
#     room_groups = defaultdict(list)
#     for slot in schedule:
#         if slot['mata_kuliah'] is None:
#             continue
#         key = (slot['ruang'], slot['hari'].lower())
#         room_groups[key].append(slot)
#     for (ruang, hari), slots in room_groups.items():
#         slots.sort(key=lambda s: time_to_minutes(s['jam_mulai']))
#         for i in range(len(slots)):
#             for j in range(i+1, len(slots)):
#                 start_i = time_to_minutes(slots[i]['jam_mulai'])
#                 end_i = time_to_minutes(slots[i]['jam_selesai'])
#                 start_j = time_to_minutes(slots[j]['jam_mulai'])
#                 if start_j < end_i and slots[i]['kelas'] != slots[j]['kelas']:
#                     tid_i = slots[i].get('temp_id')
#                     tid_j = slots[j].get('temp_id')
#                     if tid_i is not None:
#                         conflict_temp_ids.add(tid_i)
#                     if tid_j is not None:
#                         conflict_temp_ids.add(tid_j)
#                     room_conflicts.append((slots[i]['id_slot'], slots[j]['id_slot']))
    
#     # --- Preferensi Dosen ---
#     for slot in schedule:
#         if slot['mata_kuliah'] is None:
#             continue
#         start = time_to_minutes(slot['jam_mulai'])
#         tid = slot.get('temp_id')
#         dosen = str(slot['dosen'])
#         hari = slot['hari'].lower()
#         if dosen in lecturer_preferences:
#             for pref in lecturer_preferences[dosen]:
#                 violated = False
#                 if pref["type"] == "time":
#                     start_range, end_range = pref["value"]
#                     if start < start_range or start >= end_range:
#                         violated = True
#                 elif pref["type"] == "restricted_day":
#                     # Jika nilai sudah berupa list atau string
#                     if isinstance(pref["value"], list):
#                         days = pref["value"]
#                     else:
#                         days = [pref["value"]]
#                     if hari in days:
#                         violated = True
#                 if violated and tid is not None:
#                     preference_conflict_temp_ids.add(tid)

#     # --- Konflik Kelas: Jika kelas yang sama berada pada jam yang sama, semester yang sama, dan hari yang sama, maka dianggap konflik ---
#     class_conflicts = []
#     class_groups = defaultdict(list)
#     for slot in schedule:
#         if slot['mata_kuliah'] is None:
#             continue
#         key = (slot['kelas'], slot['hari'].lower(), slot['semester'])
#         class_groups[key].append(slot)
#     for key, slots in class_groups.items():
#         slots.sort(key=lambda s: time_to_minutes(s['jam_mulai']))
#         for i in range(len(slots)):
#             start_i = time_to_minutes(slots[i]['jam_mulai'])
#             end_i = time_to_minutes(slots[i]['jam_selesai'])
#             for j in range(i+1, len(slots)):
#                 start_j = time_to_minutes(slots[j]['jam_mulai'])
#                 if start_j >= end_i:
#                     break  # Tidak perlu cek slot berikutnya
#                 # Overlapping terjadi
#                 tid_i = slots[i].get('temp_id')
#                 tid_j = slots[j].get('temp_id')
#                 if tid_i is not None:
#                     conflict_temp_ids.add(tid_i)
#                 if tid_j is not None:
#                     conflict_temp_ids.add(tid_j)
#                 class_conflicts.append((slots[i]['id_slot'], slots[j]['id_slot']))
    
#     return {
#         'class_conflicts': class_conflicts,
#         'conflict_temp_ids': conflict_temp_ids,
#         'preference_conflict_temp_ids': preference_conflict_temp_ids,
#         'teacher_conflicts': teacher_conflicts,   
#         'room_conflicts': room_conflicts,           
#         'room_consistency_conflicts': room_consistency_conflicts
#     }

# def calculate_fitness(schedule):
#     conflicts = collect_conflicts(schedule)
#     penalty = 0.0
#     penalty += len(conflicts['teacher_conflicts']) * 1.0
#     penalty += len(conflicts['room_conflicts']) * 1.0
#     penalty += len(conflicts['room_consistency_conflicts']) * 1.0
#     penalty += len(conflicts['preference_conflict_temp_ids']) * 0.5
#     penalty += len(conflicts['class_conflicts']) * 1.0
#     return penalty

# class GreyWolfOptimizer:
#     def __init__(self, population_size=10, max_iterations=50):
#         self.population_size = population_size
#         self.max_iterations = max_iterations
        
#     def optimize(self, fitness_function, create_solution_function, collect_conflicts_func):
#         # Inisialisasi populasi
#         population = [create_solution_function() for _ in range(self.population_size)]
#         fitness_values = [fitness_function(solution) for solution in population]
        
#         best_solution = None
#         best_fitness = float('inf')
#         a_start = 2.0

#         fitness_history = pd.DataFrame(columns=['Iterasi', 'Best Fitness'])
        
#         for iteration in range(self.max_iterations):
#             a = a_start - iteration * (a_start / self.max_iterations)
#             if best_fitness <= 0:
#                 break
            
#             sorted_indices = np.argsort(fitness_values)
#             alpha = population[sorted_indices[0]]
#             beta = population[sorted_indices[1]]
#             delta = population[sorted_indices[2]]
#             alpha_fitness = fitness_values[sorted_indices[0]]
            
#             if alpha_fitness < best_fitness:
#                 best_fitness = alpha_fitness
#                 best_solution = copy.deepcopy(alpha)
            
#             print(f"Iterasi {iteration+1}/{self.max_iterations} - Best Fitness: {best_fitness}")
            
#             new_population = []
#             for i in range(self.population_size):
#                 # Dengan probabilitas kecil lakukan random restart
#                 if random.random() < 0.05:
#                     new_solution = create_solution_function()
#                 else:
#                     new_solution = self.update_position(population[i], alpha, beta, delta, a, create_solution_function, fitness_function)
#                 new_population.append(new_solution)
#                 fitness_values[i] = fitness_function(new_solution)
            
#             population = new_population

#             # Simpan data iterasi ke DataFrame (tidak dibuat ulang setiap iterasi)
#             fitness_history.loc[iteration, 'Iterasi'] = iteration + 1
#             fitness_history.loc[iteration, 'Best Fitness'] = best_fitness
        
#         print("Optimasi Selesai!")
#         print(f"Best Fitness: {best_fitness}")
        
#         cek_konflik = collect_conflicts_func(best_solution)
#         conflict_numbers = set()
#         print(cek_konflik)

#         # Gabungkan semua angka dari semua jenis konflik
#         for key, value in cek_konflik.items():
#             if isinstance(value, (set, list)):
#                 conflict_numbers.update(map(str, value))  # Ubah semua angka ke string untuk konsistensi

#         # Tandai jadwal dengan status 'code_red' jika 'temp_id' sama persis dengan angka konflik
#         for slot in best_solution:
#             temp_id = str(slot.get("temp_id", ""))
#             if temp_id in conflict_numbers:
#                 if temp_id in map(str, cek_konflik['conflict_temp_ids']):
#                     status = "red"
#                 elif temp_id in map(str, cek_konflik['preference_conflict_temp_ids']):
#                     status = "yellow"
#                 else:
#                     continue
                
#                 if "status" in slot and slot["status"]:
#                     if status not in slot["status"]:
#                         slot["status"] += f", {status}"
#                 else:
#                     slot["status"] = status
#         return best_solution, best_fitness, fitness_history
    
#     def update_position(self, current_solution, alpha, beta, delta, a, create_solution_function, fitness_function):
#         new_solution = copy.deepcopy(current_solution)
        
#         # Dapatkan temp_id yang mengalami konflik dari solusi saat ini
#         conflicts = collect_conflicts(new_solution)
#         conflict_temp_ids = conflicts.get('conflict_temp_ids', set())
        
#         # Jika tidak ada konflik, kembalikan solusi tanpa perubahan
#         if not conflict_temp_ids:
#             return new_solution
        
#         # Fokus pada setiap temp_id yang bermasalah
#         for tid in conflict_temp_ids:
#             # Dapatkan indeks slot yang memiliki temp_id ini
#             indices = [i for i, slot in enumerate(new_solution) if slot.get('temp_id') == tid]
#             if not indices:
#                 continue 
            
#             candidate = None
#             for source in [alpha, beta, delta]:
#                 source_block = [slot for slot in source if slot.get('temp_id') == tid]
#                 if source_block:
#                     candidate = source_block[0]
#                     break
            
#             if candidate is not None:
#                 course_info = {
#                     'id_mk': candidate['id_mk'],
#                     'mata_kuliah': candidate['mata_kuliah'],
#                     'id_dosen': candidate['id_dosen'],
#                     'dosen': candidate['dosen'],
#                     'kelas': candidate['kelas'],
#                     'sks': candidate['sks'],
#                     'semester': candidate['semester'],
#                     'metode': candidate['metode'],
#                     'temp_id': candidate['temp_id']
#                 }
#                 # Buat salinan sementara dari solusi untuk mencoba repair
#                 temp_solution = copy.deepcopy(new_solution)
#                 # Reset blok pada temp_solution
#                 for idx in indices:
#                     temp_solution[idx].update({
#                         "id_mk": None,
#                         "mata_kuliah": None,
#                         "id_dosen": None,
#                         "dosen": None,
#                         "kelas": None,
#                         "sks": None,
#                         "semester": None,
#                         "metode": None,
#                         "temp_id": None
#                     })
#                 # Coba jadwalkan ulang kursus pada temp_solution dengan opsi relax
#                 repair_attempts = 5
#                 success = False
#                 for _ in range(repair_attempts):
#                     if self.schedule_course(temp_solution, course_info, relax=True):
#                         success = True
#                         break
#                 if not success:
#                     # Jika repair dengan relax gagal, coba dengan force
#                     if self.schedule_course(temp_solution, course_info, force=True):
#                         success = True
#                 # Jika berhasil, update new_solution dengan temp_solution untuk blok tersebut
#                 if success:
#                     new_solution = temp_solution
#                 # Jika tidak berhasil, biarkan blok asli tidak diubah (tidak direset)
        
#         return new_solution
    
#     def schedule_course(self, schedule, course, force=False, relax=False):
#         id_mk = course['id_mk']
#         mata_kuliah = course['mata_kuliah']
#         id_dosen = course['id_dosen']
#         dosen = course['dosen']
#         kelas = course['kelas']
#         sks = course['sks']
#         semester = course['semester']
#         metode = course['metode']
#         temp_id = course['temp_id']
        
#         possible_positions = []
#         for i in range(len(schedule) - sks + 1):
#             block = schedule[i:i+sks]
#             if not all(slot['mata_kuliah'] is None for slot in block):
#                 continue
#             if not all(slot['hari'] == block[0]['hari'] for slot in block):
#                 continue
#             if not all(slot['ruang'] == block[0]['ruang'] for slot in block):
#                 continue

#             valid = True
#             for j in range(1, len(block)):
#                 time_diff = abs(time_to_minutes(block[j]['jam_mulai']) - time_to_minutes(block[j-1]['jam_selesai']))
#                 if not relax and time_diff != 0:
#                     valid = False
#                     break
#                 elif relax and time_diff > 5:
#                     valid = False
#                     break
#             if valid:
#                 possible_positions.append(i)
        
#         if possible_positions:
#             pos = random.choice(possible_positions)
#             block = schedule[pos:pos+sks]
#             for slot in block:
#                 slot.update({
#                     "id_mk": id_mk,
#                     "mata_kuliah": mata_kuliah,
#                     "id_dosen": id_dosen,
#                     "dosen": dosen,
#                     "kelas": kelas,
#                     "sks": sks,
#                     "semester": semester,
#                     "metode": metode,
#                     "temp_id": temp_id
#                 })
#             return True
        
#         if force and sks == 1:
#             empty_slots = [i for i, slot in enumerate(schedule) if slot['mata_kuliah'] is None]
#             if empty_slots:
#                 pos = random.choice(empty_slots)
#                 schedule[pos].update({
#                     "id_mk": id_mk,
#                     "mata_kuliah": mata_kuliah,
#                     "id_dosen": id_dosen,
#                     "dosen": dosen,
#                     "kelas": kelas,
#                     "sks": sks,
#                     "semester": semester,
#                     "metode": metode,
#                     "temp_id": temp_id
#                 })
#                 return True
        
#         return False

# def run_gwo_optimization(create_random_schedule_func, calculate_fitness_func, collect_conflicts_func, population_size=10, max_iterations=100):
#     gwo = GreyWolfOptimizer(population_size, max_iterations)
#     best_solution, best_fitness, fitness_history = gwo.optimize(calculate_fitness_func, create_random_schedule_func, collect_conflicts_func)
#     return best_solution, best_fitness, fitness_history

# if __name__ == "__main__":
#     population_size = 30
#     max_iterations = 30
#     num_experiments = 30
#     data_rows = []

#     for i in range(num_experiments):
#         best_schedule, best_fitness, fitness_history = run_gwo_optimization(
#             create_random_schedule,
#             calculate_fitness,
#             collect_conflicts,
#             population_size=population_size,
#             max_iterations=max_iterations
#         )
#         print(f"Experiment {i+1}/{num_experiments} - Best Fitness: {best_fitness}")
#         data_rows.append(fitness_history['Best Fitness'].tolist())

#     row1 = [f"individu {population_size}"] * max_iterations
#     # Baris kedua: label iterasi
#     row2 = [f"Iterasi {i+1}" for i in range(max_iterations)]
    
#     all_rows = [row1, row2] + data_rows
#     df = pd.DataFrame(all_rows)
    
#     excel_file = "revisi populasi 30 iterasi 30.xlsx"
#     df.to_excel(excel_file, header=False, index=False)
#     print(f"File Excel berhasil dibuat: {excel_file}")