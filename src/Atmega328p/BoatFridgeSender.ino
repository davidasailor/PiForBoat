#include <SPI.h>
#include <RH_RF69.h>
#include <LowPower.h>
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>

#define DEBUG         0

#define RFM69_INT     3   
#define RFM69_CS      4  
#define RFM69_RST     2  
#define LED           13
#define RADIO_EN      9
#define THERM_PIN     8

RH_RF69 rf69(RFM69_CS, RFM69_INT);

uint8_t key[] = { 0x26, 0x26, 0x26, 0x26, 0x26, 0x26, 0x26, 0x26,
                  0x26, 0x26, 0x26, 0x26, 0x26, 0x26, 0x26, 0x26};

OneWire oneWire(THERM_PIN);
DallasTemperature sensors(&oneWire);

void setup() 
{
  #if DEBUG
    Serial.begin(115200);
  #endif
  
  pinMode(LED, OUTPUT);
  pinMode(RFM69_RST, OUTPUT);
  pinMode(RADIO_EN, OUTPUT);
  
  Wire.begin();
  sensors.begin();
}


void loop()
{

  #if DEBUG
    Serial.println("Preparing to read thermometer");
  #endif

  sensors.requestTemperatures();

  float tempF = sensors.getTempFByIndex(0);
  int temp = 0;

  // Check if reading was successful
  if(tempF != DEVICE_DISCONNECTED_F) 
  {
    temp = round(tempF);
  } 


  #if DEBUG
    Serial.print("Therm Val: ");
    Serial.println(temp);
  #endif

  digitalWrite(RADIO_EN, HIGH);
    
  // manual reset
  digitalWrite(RFM69_RST, HIGH);
  delay(10);
  digitalWrite(RFM69_RST, LOW);
  delay(10);

  #if DEBUG
  Serial.println("Initializing radio");
  #endif
  
  rf69.init();
  
  rf69.setFrequency(433.0);

  rf69.setTxPower(14, true);

  rf69.setEncryptionKey(key);

  #if DEBUG
  Serial.println("Sending to rf69_server");
  #endif

  
  uint8_t data[] = {0x0, 0x1, 0x0, 0x0, byte(temp), 0x0};
  
  rf69.send(data, sizeof(data));
  rf69.waitPacketSent();

  digitalWrite(RADIO_EN, LOW);
  
  #if DEBUG
  Serial.println("Sent; going to sleep");
  Serial.flush();
  #endif
  
  LowPower.powerDown(SLEEP_8S, ADC_OFF, BOD_OFF);  

}
