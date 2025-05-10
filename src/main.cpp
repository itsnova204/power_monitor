#include <Arduino.h>
#include <SoftwareSerial.h>
#include <ModbusMaster.h>
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <ArduinoJson.h> 

#define DEVICE_NAME "PZEM004T_ESP8266_01"

// --- WiFi Credentials ---
const char* ssid = "";
const char* password = "";

// --- Ingest Server Details ---
const char* serverHost = "<ip>"; // "192.168.1.1"
const int serverPort = 5000; 
const char* serverPath = "/data";

//pins for PZEM communication
#define PZEM_RX_PIN D5 
#define PZEM_TX_PIN D6
#define PZEM_SLAVE_ADDRESS 0x01

SoftwareSerial pzemSerial(PZEM_RX_PIN, PZEM_TX_PIN);
ModbusMaster node;

void connectToWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

void setup() {
  Serial.begin(115200);
  while (!Serial) { ; }
  Serial.println("ESP8266 PZEM-004T Data Logger V1.2");

  connectToWiFi();

  pzemSerial.begin(9600);
  node.begin(PZEM_SLAVE_ADDRESS, pzemSerial);
}

void loop() { //FutureWork: add button to reset the pzem
  uint8_t result;

  result = node.readInputRegisters(0x0000, 10); //read the 10 registers

  if (result == node.ku8MBSuccess) {
    Serial.println("--------------------");
    Serial.println("Modbus Read Successful!");

    float voltage = node.getResponseBuffer(0) / 10.0;
    uint32_t current_raw = ((uint32_t)node.getResponseBuffer(2) << 16) | node.getResponseBuffer(1);
    float current = current_raw / 1000.0;
    uint32_t power_raw = ((uint32_t)node.getResponseBuffer(4) << 16) | node.getResponseBuffer(3);
    float power = power_raw / 10.0;
    uint32_t energy_raw = ((uint32_t)node.getResponseBuffer(6) << 16) | node.getResponseBuffer(5);
    float energy = (float)energy_raw;
    float frequency = node.getResponseBuffer(7) / 10.0;
    float powerFactor = node.getResponseBuffer(8) / 100.0;
    uint16_t alarmStatus_raw = node.getResponseBuffer(9);
    bool isAlarm = (alarmStatus_raw == 0xFFFF);

    Serial.print("Voltage: "); Serial.print(voltage, 1); Serial.println(" V");
    
    
    DynamicJsonDocument jsonDoc(512); 
    jsonDoc["voltage"] = voltage;
    jsonDoc["current"] = current;
    jsonDoc["power"] = power;
    jsonDoc["energy"] = energy;
    jsonDoc["frequency"] = frequency;
    jsonDoc["powerFactor"] = powerFactor;
    jsonDoc["alarmStatus"] = isAlarm; 
    jsonDoc["deviceId"] = DEVICE_NAME; 

    String jsonData;
    serializeJson(jsonDoc, jsonData);
    Serial.print("Sending JSON: ");
    Serial.println(jsonData);

    if (WiFi.status() == WL_CONNECTED) {
      WiFiClient client; 
      HTTPClient http;   

      String serverUrl = "http://" + String(serverHost) + ":" + String(serverPort) + String(serverPath);
      Serial.print("POST to URL: "); Serial.println(serverUrl);

      http.begin(client, serverUrl); // Specify WiFiClient and URL
      http.addHeader("Content-Type", "application/json");

      int httpResponseCode = http.POST(jsonData);

      if (httpResponseCode > 0) {
        Serial.print("HTTP Response code: ");
        Serial.println(httpResponseCode);
        String payload = http.getString();
        Serial.println(payload);
      } else {
        Serial.print("Error on sending POST: ");
        Serial.println(httpResponseCode);
        Serial.printf("[HTTP] POST... failed, error: %s\n", http.errorToString(httpResponseCode).c_str());
      }
      http.end();
    } else {
      Serial.println("WiFi Disconnected. Cannot send data.");
      connectToWiFi();
    }

  } else {
    Serial.print("Modbus Read Failed. Error code: 0x");
    Serial.println(result, HEX);
     if (result == node.ku8MBResponseTimedOut) {
      Serial.println(" (Response Timed Out)");
    } 
  }
  delay(1000); 
}