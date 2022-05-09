# PROGETTO
# Created at 2021-06-17 08:21:06.000347

from zdm import zdm
import LCD_1602
import ultrasuoni
import streams
import adc
import i2c
import threading
from maxim.ds1307 import ds1307
from wireless import wifi
from mqtt import mqtt
from meas.htu21d import htu21d
from espressif.esp32net import esp32wifi as wifi_driver
from mqtt import mqtt

streams.serial()

wifi_driver.auto_init()
ssid="ASUS_68_2G"
psw="2010casa"
# (display) LCD1602 >> I2C1
# (temp) HTU21D, (timer) DS1307 >> I2C0 
# pin water level sensor
water=A0
# pin pompetta irrigazione
pompa=D13
# pin sensore ad ultrasuoni
echo=D23
trig=D22
# altezza (in cm) del contenitore per prelevare l'acqua
altezza=20
# pin led
verde=D12
rosso=D15

pinMode(verde,OUTPUT)
pinMode(rosso,OUTPUT)
pinMode(pompa,OUTPUT)
digitalWrite(verde,LOW)
digitalWrite(rosso,LOW)
digitalWrite(pompa,LOW)


non_piove=True
tupla=()
sensor_lock = threading.Lock()

ultrasuoni=ultrasuoni.hcsr04(trig,echo)

try:
    display=LCD_1602.lcd(I2C1)
    display.clear()
except Exception as e:
    print("Error Starting Display: ",e)


try:
    htu = htu21d.HTU21D(I2C0)
    htu.start()
    htu.init()
except Exception as e:
    print("Error starting HTU21D: ",e)


try:
    timer = ds1307.DS1307(I2C0)
    # set_time(hours, minutes, seconds, day, month, year, day_of_week)
    timer.set_time(0,0,0,1,1,2021,5)
except Exception as e:
    print("Error starting DS1307: ",e)


def stampa(stringa):
    display.clear()
    display.message(stringa)


def connessione (ssid,psw):
    print("Establishing Link...")
    for retry in range(5):
        try:
            wifi.link(ssid,wifi.WIFI_WPA2,psw)
            break
        except Exception as e:
            print("ooops, something wrong while linking :(", e)
    print("Link Established")
    sleep(2000)


def truncate(num, n):
    integer = int(num * (10**n))/(10**n)
    return float(integer)

def rain_check():
    global non_piove
    res=adc.read(water)
    if res>=300:
        stampa("Piove\nNon Irrigo")
        non_piove=False
    else:
        non_piove=True


def irriga():
    digitalWrite(verde,HIGH)
    digitalWrite(pompa,HIGH)
    print("Irrigo\n")
    stampa("Irrigo")
    sleep(4000)
    digitalWrite(verde,LOW)
    digitalWrite(pompa,LOW)


def check_HTU21D():
    t,h = htu.get_temp_humid()
    print("Temperature: %.2f C Humidity: %.2f " %(t,h) + "%")
    stampa("Temp: %.2f C\nHum: %.2f " %(t,h) + "%")
    if ((t>30 or h<50) and non_piove):
        irriga()
    return truncate(t,2),truncate(h,2)

def water_level_check():
    x=int(ultrasuoni.getDistanceCM())
    y=(100*x)/(altezza)
    if (y<=100):
        lvl=100-y
        if (lvl>=30):
            stampa("Water Level:\n" + str(lvl) + " %")
            digitalWrite(rosso,LOW)
        else:
            stampa("Water Level\ncritico Riempire")
            digitalWrite(rosso,HIGH)
        return lvl
    else:
        stampa("Misura Water\nLevel Error")
        digitalWrite(rosso,HIGH)
        return 0


def check_DS1307():
    global tupla
    tupla=timer.get_time()
    print("%02d:%02d:%02d - %02d/%02d/%d - %d"%tupla)
    #tupla[2]>=30
    if (tupla[3]>=4 and non_piove):
        timer.set_time(0,0,0,1,1,2021,5)
        irriga()


def jpump(device,arg):
    if "pump" in arg:
        sensor_lock.acquire()
        if arg["pump"] == "irriga":
            digitalWrite(verde,HIGH)
            digitalWrite(pompa,HIGH)
            stampa("Irrigo da ZDM")
            sleep(4000)
            digitalWrite(verde,LOW)
            digitalWrite(pompa,LOW)
            val = "irrigazione effettuata"
        else:
            val = "error"
        sensor_lock.release()
    return {arg["pump"]: val}


my_jobs={"remote_watering": jpump}


irrigo= False


def condition_handler(condition_true, condition_tag, open_message="Condition open", close_message="Condition close"):
    if condition_true and not condition_tag.is_open():
        condition_tag.open(payload={"Status": open_message})
    elif not condition_true and condition_tag.is_open():
        condition_tag.close(payload={"Status": close_message})
        condition_tag.reset()

COND_TAGS = ["irrigazione"]


def pub_data():
    while True:
        try:
            print("-----publish sensors reading-----")
            tag = 'data'
            payload = {}
            
            sensor_lock.acquire()
            rain_check()
            sleep(500)
            t,h=check_HTU21D()
            sleep(500)
            l=water_level_check()
            check_DS1307()
            sensor_lock.release()
            
            payload = {
                'temp' : t, 
                'hum' : h,
                'water' : l
            }
            
            irrigo = ((t>30 or h<50) or tupla[3]>=4) and non_piove
            condition_handler(irrigo,non_irrigo,open_message="Irrigo",close_message="Finito")
            
            try:
                device.publish(payload,tag)
                print('published on tag: ', tag, ":", payload)
            except Exception as e:
                print('Publish error: ', e)
        except Exception as e:
            print("Loop error: ",e)
        sleep(5000)


connessione(ssid,psw)
device = zdm.Device(jobs_dict = my_jobs,condition_tags = COND_TAGS)
device.connect()
non_irrigo=device.new_condition("irrigazione")

pub_data()

