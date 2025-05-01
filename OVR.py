import os
import sys
import ctypes
import shutil
import subprocess
import configparser
import webbrowser
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pystray
from PIL import Image, ImageDraw, ImageTk

# Импорт модулей для работы с Windows API и системного трея
try:
    import win32api
    import win32con
    import win32gui
    import pywintypes
except ImportError:
    print("Ошибка: требуется модуль pywin32. Установите его: pip install pywin32")
    sys.exit(1)

# Проверка наличия модулей pystray и Pillow выполнена выше (они необходимы для работы с системным треем)
try:
    from PIL import Image
except ImportError:
    print("Ошибка: требуется Pillow. Установите его: pip install Pillow")

    sys.exit(1)

def custom_show_error(title, message):
    popup = tk.Toplevel(root)
    popup.title(title)
    popup.configure(bg="#2e2e2e")
    popup.resizable(False, False)
    try:
        popup.iconbitmap("_internal\\my_tk_icon.ico")  # путь к вашей иконке для всплывающих окон
    except Exception:
        pass
    lbl = tk.Label(popup, text=message, font=("Helvetica", 12), bg="#2e2e2e", fg="#ffffff")
    lbl.pack(padx=20, pady=20)
    btn = ttk.Button(popup, text="OK", command=popup.destroy)
    btn.pack(pady=10)
    popup.grab_set()
    popup.wait_window()

def custom_show_info(title, message):
    popup = tk.Toplevel(root)
    popup.title(title)
    popup.configure(bg="#2e2e2e")
    popup.resizable(False, False)
    try:
        popup.iconbitmap("_internal\\my_tk_icon.ico")
    except Exception:
        pass
    lbl = tk.Label(popup, text=message, font=("Helvetica", 12), bg="#2e2e2e", fg="#ffffff")
    lbl.pack(padx=20, pady=20)
    btn = ttk.Button(popup, text="OK", command=popup.destroy)
    btn.pack(pady=10)
    popup.grab_set()
    popup.wait_window()



##########################################
# Проверка прав администратора
##########################################
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit(0)


##########################################
# Проверка наличия утилиты DevCon
##########################################
if shutil.which("devcon") is None:
    tk.Tk().withdraw()
    
    # Функция кастомного всплывающего окна "Перезагрузка"
    def show_custom_popup():
        popup = tk.Toplevel()
        popup.title("Перезагрузка")
        popup.geometry("400x200")
        popup.resizable(False, False)
        popup.configure(bg="#2e2e2e")

        # Устанавливаем кастомную иконку
        popup.iconbitmap("_internal\\my_tk_icon.ico")

        # Загружаем PNG-иконку, если она есть
        img = Image.open("_internal\\my_tk_icon.png").resize((32, 32))
        icon = ImageTk.PhotoImage(img)

        # Вставляем иконку в окно
        lbl_icon = tk.Label(popup, image=icon, bg="#2e2e2e")
        lbl_icon.image = icon  # Сохраняем ссылку, чтобы не удалилось
        lbl_icon.pack(pady=10)

        # Текст сообщения
        label_text = ttk.Label(popup, text="DevCon не найден! \nБудет открыта страница установки DevCon-Installer.\nУстановите DevCon в System32.\nПерезагрузите компьютер и запустите программу снова.", foreground="white", background="#2e2e2e")
        label_text.pack(pady=5)
        webbrowser.open("https://github.com/Drawbackz/DevCon-Installer")
        

        # Кнопка закрытия окна
        btn_close = ttk.Button(popup, text="Закрыть", command=popup.destroy)
        btn_close.pack(pady=10)

        popup.mainloop()
        
    
    # Показываем кастомное всплывающее окно "Перезагрузка"
    show_custom_popup()
    sys.exit(1)


##########################################
# Загрузка и сохранение конфигурации (Documents\OneS)
##########################################
def get_config_dir():
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.cfg")
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    return config_dir

CONFIG_FILE = os.path.join(get_config_dir(), "config.cfg")
config = configparser.ConfigParser()
default_width = "1280"
default_height = "1024"
stored_program_path = ""
stored_width = default_width
stored_height = default_height

if os.path.exists(CONFIG_FILE):
    config.read(CONFIG_FILE)
    stored_program_path = config.get('Settings', 'program_path', fallback="")
    stored_width = config.get('Settings', 'width', fallback=default_width)
    stored_height = config.get('Settings', 'height', fallback=default_height)


##########################################
# Глобальные переменные
##########################################
monitor_ids_list = []
original_devmode = None


##########################################
# Функция поиска всех подключённых мониторов
##########################################
def find_all_monitors():
    monitors = []
    adapter_index = 0
    while True:
        try:
            adapter = win32api.EnumDisplayDevices(None, adapter_index)
        except pywintypes.error:
            break  # Больше адаптеров
        monitor_index = 0
        while True:
            try:
                monitor = win32api.EnumDisplayDevices(adapter.DeviceName, monitor_index)
            except pywintypes.error:
                break  # Больше устройств для данного адаптера
            if monitor.DeviceID and "MONITOR" in monitor.DeviceID.upper():
                monitors.append(monitor.DeviceID)
            monitor_index += 1
        adapter_index += 1
    return monitors


##########################################
# Функция восстановления исходного состояния
##########################################
def cleanup():
    global monitor_ids_list, original_devmode
    for device_id in monitor_ids_list:
        print("Включаем монитор с ID:", device_id)
        proc_enable = subprocess.run(["devcon", "enable", device_id[:15]],
                                     capture_output=True, text=True)
        print(proc_enable.stdout)
        time.sleep(1)
    if original_devmode:
        win32api.ChangeDisplaySettings(original_devmode, 0)
        print("Исходное разрешение восстановлено.")

def is_process_running(process_name):
    try:
        output = subprocess.check_output(
            ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
            universal_newlines=True
        )
        lines = output.splitlines()
        # Обычно, если процесс не найден, вывод содержит одну или две строки.
        # Если их больше (например, 3 и более), значит процесс запущен.
        if len(lines) >= 3:
            return True
        return False
    except Exception:
        return False



##########################################
# Основная процедура: изменение разрешения, отключение мониторов,
# запуск внешней программы и ожидание завершения
##########################################
def start_main_process(prog_path, new_width, new_height):
    global monitor_ids_list, original_devmode

    # Получаем имя исполняемого файла (например, "game.exe")
    exe_name = os.path.basename(prog_path)

    

    # Если процесс уже запущен – выводим окно, которое просит закрыть приложение.
    # Цикл будет повторяться до тех пор, пока указанное приложение не будет закрыто.
    while is_process_running(exe_name):
        custom_show_info("Приложение уже запущено",
                         f"Приложение '{exe_name}' уже запущено.\nПожалуйста, закройте его и нажмите OK, чтобы продолжить.")

    # Если процесс не запущен, продолжаем выполнение:
    monitor_ids_list = find_all_monitors()
    if not monitor_ids_list:
        custom_show_error("Ошибка", "Система не обнаружила ни одного монитора для отключения.")
        return
    else:
        print("Найденные мониторы:")
        for mid in monitor_ids_list:
            print(mid)
    # Сохраняем исходное разрешение
    original_devmode = win32api.EnumDisplaySettings(None, win32con.ENUM_CURRENT_SETTINGS)
    print("Исходное разрешение: {} x {}".format(original_devmode.PelsWidth, original_devmode.PelsHeight))
    # Изменяем разрешение
    new_devmode = win32api.EnumDisplaySettings(None, win32con.ENUM_CURRENT_SETTINGS)
    new_devmode.PelsWidth = new_width
    new_devmode.PelsHeight = new_height
    new_devmode.Fields = win32con.DM_PELSWIDTH | win32con.DM_PELSHEIGHT
    result = win32api.ChangeDisplaySettings(new_devmode, 0)
    if result != win32con.DISP_CHANGE_SUCCESSFUL:
        custom_show_error("Ошибка", f"Не удалось изменить разрешение на {new_width}x{new_height}.")
        return
    print("Разрешение изменено на {} x {}.".format(new_width, new_height))
    # Отключаем все найденные мониторы (используем усечение идентификатора)
    for device_id in monitor_ids_list:
        print("Отключаем монитор с ID:", device_id)
        proc = subprocess.run(["devcon", "disable", device_id[:15]],
                              capture_output=True, text=True)
        print(proc.stdout)
        time.sleep(1)
    # Запускаем внешнюю программу
    try:
        proc = subprocess.Popen(prog_path)
        print("Запущена программа:", prog_path)
    except Exception as e:
        custom_show_error("Ошибка", f"Не удалось запустить программу:\n{prog_path}\nОшибка: {e}")
        cleanup()
        return
    # Пытаемся свернуть окно (если активно)
    try:
        hwnd = win32gui.GetForegroundWindow()
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
    except Exception as e:
        print("Не удалось свернуть окно:", e)
    # Запускаем поток, который ждёт завершения внешней программы и затем вызывает cleanup
    def wait_and_cleanup():
        proc.wait()
        print("Внешняя программа завершила работу.")
        cleanup()
    threading.Thread(target=wait_and_cleanup, daemon=True).start()



##########################################
# Функции для значка в системном трее и его меню
##########################################
def create_image():
    # Загружаем свою иконку для системного трея (my_tray_icon.ico)
    return Image.open("_internal\\my_tray_icon.ico").resize((64, 64))

def on_tray_open(icon, item):
    # При клике на пункт меню "Открыть настройки" возвращаем окно настроек
    root.deiconify()

def on_tray_exit(icon, item):
    cleanup()
    icon.stop()
    root.quit()

tray_menu = pystray.Menu(
    pystray.MenuItem("Открыть настройки", on_tray_open),
    pystray.MenuItem("Выход", on_tray_exit)
)
tray_icon = pystray.Icon("OneS valres", create_image(), "OneS valres", menu=tray_menu)

def run_tray_icon():
    tray_icon.run_detached()
threading.Thread(target=run_tray_icon, daemon=True).start()


##########################################
# Интерфейс настроек на Tkinter (с тёмной темой и фиксированным размером)
##########################################
root = tk.Tk()
root.title("OneS valres")
root.geometry("550x200")
root.configure(bg="#2e2e2e")
root.resizable(False, False)  # Окно неизменяемого размера

# Устанавливаем иконку для окна (иконка в левом верхнем углу)
root.iconbitmap("_internal\\my_tk_icon.ico")

# Общая тёмная палитра для окна и диалогов
root.tk_setPalette(background="#2e2e2e", foreground="#ffffff",
                   activeBackground="#454545", activeForeground="#ffffff")
root.option_add("*Dialog.msg.font", ("Helvetica", 12))
root.option_add("*Dialog.msg.background", "#2e2e2e")
root.option_add("*Dialog.msg.foreground", "#ffffff")
root.option_add("*Toplevel*background", "#2e2e2e")

style = ttk.Style(root)
style.theme_use('clam')
style.configure("TFrame", background="#2e2e2e")
style.configure("TLabel", background="#2e2e2e", foreground="#ffffff")
style.configure("TEntry", fieldbackground="#3c3c3c", foreground="#ffffff")
style.configure("TButton", background="#3c3c3c", foreground="#ffffff")
style.map("TButton", background=[('active', '#4a4a4a')])

main_frame = ttk.Frame(root, padding="10")
main_frame.pack(fill=tk.BOTH, expand=True)

label_resolution = ttk.Label(main_frame, text="Разрешение:")
label_resolution.grid(row=0, column=0, sticky=tk.W, pady=5)
entry_width = ttk.Entry(main_frame, width=10)
entry_width.insert(0, stored_width)
entry_width.grid(row=0, column=1, sticky=tk.W, padx=5)
label_x = ttk.Label(main_frame, text="x")
label_x.grid(row=0, column=2, sticky=tk.W)
entry_height = ttk.Entry(main_frame, width=10)
entry_height.insert(0, stored_height)
entry_height.grid(row=0, column=3, sticky=tk.W, padx=5)

label_program = ttk.Label(main_frame, text="Игра:")
label_program.grid(row=1, column=0, sticky=tk.W, pady=5)
entry_program = ttk.Entry(main_frame, width=40)
entry_program.grid(row=1, column=1, columnspan=3, sticky=tk.W, padx=5)
if stored_program_path:
    entry_program.insert(0, stored_program_path)

def choose_program():
    path = filedialog.askopenfilename(title="Выберите программу",
                                      filetypes=[("Исполняемые файлы (.exe)", "*.exe"), ("Все файлы", "*.*")])
    if path:
        entry_program.delete(0, tk.END)
        entry_program.insert(0, path)

btn_choose = ttk.Button(main_frame, text="Выбрать...", command=choose_program)
btn_choose.grid(row=1, column=4, padx=5)\




def on_save():
    prog = entry_program.get().strip()
    width_str = entry_width.get().strip()
    height_str = entry_height.get().strip()
    if not prog or not os.path.isfile(prog):
        custom_show_error("Ошибка", "Укажите корректный путь к программе!")
        return
    if not width_str.isdigit() or not height_str.isdigit():
        custom_show_error("Ошибка", "Разрешение должно быть числовым!")
        return
    config['Settings'] = {'program_path': prog, 'width': width_str, 'height': height_str}
    with open(CONFIG_FILE, 'w') as cfg:
        config.write(cfg)
    custom_show_info("Сохранено", "Настройки успешно сохранены!")


btn_save = ttk.Button(main_frame, text="Сохранить параметры", command=on_save)
btn_save.grid(row=2, column=0, columnspan=2, pady=20)

def on_launch():
    prog = entry_program.get().strip()
    width_str = entry_width.get().strip()
    height_str = entry_height.get().strip()
    if not prog or not os.path.isfile(prog):
        custom_show_error("Ошибка", "Необходимо указать корректный путь к программе!")
        return
    if not width_str.isdigit() or not height_str.isdigit():
        custom_show_error("Ошибка", "Разрешение должно быть числовым!")
        return
    config['Settings'] = {'program_path': prog, 'width': width_str, 'height': height_str}
    with open(CONFIG_FILE, 'w') as cfg:
        config.write(cfg)
    root.withdraw()
    # Запускаем основную процедуру в отдельном потоке, чтобы не блокировать главный цикл
    threading.Thread(target=start_main_process, args=(prog, int(width_str), int(height_str)), daemon=True).start()


btn_launch = ttk.Button(main_frame, text="Запуск", command=on_launch)
btn_launch.grid(row=2, column=3, columnspan=2, pady=20)

# Если в конфигурации уже сохранены корректные параметры, запускаем приложение моментально

root.deiconify()

root.mainloop()
