import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime
hhmm=0

class ActivimeterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("VIK-202")
        self.root.geometry("700x700")  

        self.serial_connection = None
        self.running = False

        self.isotope_commands = {
            "Tc-99m": "!F236",
            "I-123": "!F618",
            "Ga-67": "!F287",
            "In-111": "!F676",
            "Y-90": "!F902",
            "I-131": "!F447",
            "Tl-201": "!F552",
            "F-18": "!F762",
            "Cs-137": "!F587"
        }
        self.isotope_decay = {
            "Tc-99m": "0.001917",
            "I-123": "0.000873",
            "Ga-67": "0.0001476",
            "In-111": "0.000172",
            "Y-90": "0.000180",
            "I-131": "0.00006",
            "Tl-201": "0.0001584",
            "F-18": "0.006315",
            "Cs-137": "0.000000004368"
        }

        self.isotope_combobox=ttk.Combobox(self.root)
        
        self.create_widgets()

        self.connect_serial()
       
    def create_widgets(self):
        self.activity_label = ttk.Label(self.root, text="", font=("Arial", 20, "bold"), borderwidth=2, relief="solid")
        self.activity_label.pack(pady=20)

        self.isotope_label = ttk.Label(self.root)
        self.isotope_label.pack(pady=5)
        
        self.isotope_combobox = ttk.Combobox(self.root, values=list(self.isotope_commands.keys()), postcommand = self.new_isotope())
        self.isotope_combobox.set("Tc-99m")
        self.isotope_combobox.pack(pady=5)
        
        self.unit_label = ttk.Label(self.root)
        self.unit_label.pack(pady=5)

        self.unit_combobox = ttk.Combobox(self.root, values=["µCi","mCi", "MBq", "kBq"])
        self.unit_combobox.set("mCi")
        self.unit_combobox.pack(pady=5)

        self.fondo_state = tk.BooleanVar()
        self.fondo_toggle = ttk.Checkbutton(self.root, text="Fondo", variable=self.fondo_state, command=self.toggle_fondo, state=tk.DISABLED)
        self.fondo_toggle.pack(pady=10)

        self.autozero_button = ttk.Button(self.root, text="Autozero", command=self.autozero, state=tk.DISABLED)
        self.autozero_button.pack(pady=10)

        self.manual_command_label = ttk.Label(self.root)
        self.manual_command_label.pack(pady=5)

        self.manual_command_entry = ttk.Entry(self.root)
        self.manual_command_entry.pack(pady=5)

        self.send_command_button = ttk.Button(self.root, text="Enviar", command=self.send_manual_command, state=tk.DISABLED)
        self.send_command_button.pack(pady=10)

        self.info_button = ttk.Button(self.root, text="Info", command=self.show_info)
        self.info_button.pack(pady=10)

        self.log_label = tk.Label(self.root)
        self.log_label.pack(pady=10)

        self.log_text = tk.Text(self.root, height=10, state=tk.DISABLED)
        self.log_text.pack(pady=5)

    def connect_serial(self):
        #Detecta puertos COM abiertos y los prueba hasta comunicar con el activímetro        
        ports = serial.tools.list_ports.comports()        
        for port in ports:
            port=port.device
            self.serial_connection = serial.Serial(port=port, baudrate=9600, bytesize=serial.EIGHTBITS,
                                                   stopbits=serial.STOPBITS_ONE, parity=serial.PARITY_NONE, timeout=1)
            self.serial_connection.write(b'!BOFF\r')
            response = self.serial_connection.readline().decode('utf-8').strip()

            if response==">OK":
                self.running = True
                self.update_thread = threading.Thread(target=self.update_activity)
                self.update_thread.start()
                self.fondo_toggle.config(state=tk.NORMAL)
                self.autozero_button.config(state=tk.NORMAL)
                self.send_command_button.config(state=tk.NORMAL)
                
    def disconnect_serial(self):
        self.running = False
        if self.update_thread.is_alive():
            self.update_thread.join()
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()
        self.activity_label.config(text="")

    def update_activity(self):
        #Actualiza de forma continua la lectura, enviando el comando de factor de calibración seguido de !R. Ajusta según unidad de medida y decay.
        while self.running:
            try:
                selected_isotope = self.isotope_combobox.get()
                calibration_command = self.isotope_commands[selected_isotope] + "\r"
                self.serial_connection.write(calibration_command.encode())
                time.sleep(0.1)
                self.serial_connection.write(b'!R\r')
                response = self.serial_connection.readline().decode('utf-8').strip()
                response = response.replace(">OK\r>", "").strip()
                
                if response:
                    activity_value = float(response)
                    selected_unit = self.unit_combobox.get()
                    if selected_unit == "MBq":
                        converted_value = activity_value / 1e6
                    elif selected_unit == "kBq":
                        converted_value = activity_value / 1e3
                    elif selected_unit == "mCi":
                        converted_value = activity_value / (37 * 1e6)
                    elif selected_unit == "µCi":
                        converted_value = activity_value / (37 * 1e3)
                             
                    formatted_value = f"{converted_value:.1f} {selected_unit} {selected_isotope}"
                    self.activity_label.config(text=f"{formatted_value}", font=("Arial", 50, "bold"))
                    self.activity_label.pack(padx=1)
                    self.log_message(f"{response}")
                    
                    if hhmm!=0:
                        time_now=str(datetime.now())
                        time_now=time_now[11:16]
                        time_delta=int(time_now[0:2])*60+int(time_now[3:5])-int(hhmm[0:2])*60-int(hhmm[2:4])
                        converted_value=converted_value*2.71828**(float(self.isotope_decay[selected_isotope])*time_delta)
                        formatted_value = f"{converted_value:.1f} {selected_unit} {selected_isotope}"
                        self.log_message(f"{formatted_value} @ {hhmm[0:2]}:{hhmm[2:4]}")
                        
            except Exception as e:
                self.activity_label.config(text="-------------", font=("Arial", 20, "bold"))
                
            time.sleep(1)    
        
    def toggle_fondo(self):
        #Activa/desactiva la sustracción del fondo
        if self.fondo_state.get():
            self.serial_connection.write(b'!BON\r')
            self.log_message("!BON")
            response = self.serial_connection.readline().decode('utf-8').strip()
            self.log_message(response)
        else:
            self.serial_connection.write(b'!BOFF\r')
            self.log_message("!BOFF")
            response = self.serial_connection.readline().decode('utf-8').strip()
            self.log_message(response)

    def autozero(self):
        #Hace autozero
        try:
            self.serial_connection.write(b'!Z\r')
            self.log_message("!Z")
            time.sleep(0.1)
            response = self.serial_connection.readline().decode('utf-8').strip()
            self.log_message(response)
            self.serial_connection.write(b'!A\r')
            self.log_message("!A")
            response = self.serial_connection.readline().decode('utf-8').strip()
            self.log_message(response)
        except Exception as e:
            self.log_message(f"Error en el comando de autozero: {e}")

    def send_manual_command(self):
        #Envía de forma manual comandos de control al activímetro, así como introducción de hora de decay deseada
        global hhmm
        try:
            command = self.manual_command_entry.get()
            if command[0:3]=="*!F":
                self.isotope_commands[command] = command[1:]
                self.new_isotope()
                return
            if len(command)==5 and command[0]=="t" and int(command[1:3])<23 and int(command[3:5])<60:
                hhmm=str(command[1:5])
                return
            else:
                self.serial_connection.write((command + '\r').encode())
                self.log_message(f"{command}")
                response = self.serial_connection.readline().decode('utf-8').strip()
                self.log_message(response)
        except Exception as e:
                self.log_message(f"Error al enviar el comando manual: {e}")
                
    def new_isotope(self):
        #Actualiza lista de canales
        self.isotope_combobox['values'] = list(self.isotope_commands.keys())     

    def show_info(self):
        info_window = tk.Toplevel(self.root)
        info_window.title("Información")
        info_text = (
            "Control cámara ionización Veenstra VIK-202\n"
            "URF HGUSL 2024\n\n"
            "COMANDOS:\n"
            "!R\tvalor actividad (Bq)\n"
            "!BON\tbackground ON\n"
            "!BOFF\tbackground OFF\n"
            "!Z\tautozero\n"
            "!A\tresultado autozero\n"
            "!V\tvoltaje pila HV\n"
            "!GQ\tcorriente de cámara en amperios\n"
            "!GE1\tvalor bias\n"
            "!P1XX\tajuste bias (XX=valor deseado)\n"
            "!GV\tversión software\n"
            "!GP\tvalor preamplificador\n"
            "!GI\tvalor I to UB\n"
            "!GF\tvalor factor de calibración\n"
            "!GH\tganancia alta energía\n"
            "!GL\tganancia baja energía\n"
            "!F236\tcanal 99mTc\n"
            "!F618\tcanal 123I\n"
            "!F287\tcanal 67Ga\n"
            "!F676\tcanal 111In\n"
            "!F902\tcanal 90Y\n"
            "!F447\tcanal 131I\n"
            "!F552\tcanal 201Tl\n"
            "!F762\tcanal 18F\n"
            "!F587\tcanal 137Cs\n"
            "!F889\tcanal ganancia HE\n"
            "!F380\tcanal ganancia LE\n"
            "*!FX\tañadir canal (X=factor de calibración)\n"
            "thhmm\tmostrar decay en consola"
        )
        info_label = tk.Label(info_window, text=info_text, justify=tk.LEFT)
        info_label.pack(padx=10, pady=10)

    def log_message(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + '\n')
        self.log_text.config(state=tk.DISABLED)
        self.log_text.yview(tk.END)

    def on_closing(self):
        self.disconnect_serial()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ActivimeterApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
