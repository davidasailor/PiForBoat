# PiForBoat
Code and documentation for a Raspberry Pi based boat monitoring system

<H2>Concept of Operations</h2>
A central Pi mounted on the boat runs SignalK and InfluxDB.  The Pi runs a custom Python based service to read voltages and sensor data for sensors that are close to it.  Other sensors around the boat transmit data via RFM69 radio modules back to the Pi.  The Pi stores data in a log file in NMEA0183 style format, and into the InfluxDB via SignalK.  SignalK also reads all NMEA2000 data on the boat's network via a Yacht Devices USB/NMEA2K gateway.  The gateway is also used to push sensor data back out to the NMEA2K network for display on the boat's chart plotter.

In addition to the logging and network communications functions, the central Pi also gathers the following data:
  - Bilge pump runs, based on the power line to the pump from the existing electronic flow switch.  The power line to the pump goes through a voltage divider to an interrupt pin on the Pi to increment a counter and log the times of pump runs 
  - Temperatures of the cabin, engine, and exhaust elbow via DS18B20 temperature sensors
  - Water tank levels, by measuring the voltage output of existing VDO tank sensors
  - Cabin VOC's via a MiCS5524 sensor
  - Boat heel angle via an ADXL345 accelerometer

The most significant remote node is a Pi Pico.  The Pico runs a CircuitPython script to gather the following data and transmit it via RFM69HCW radio module to the main Pi for logging:
  - Data from a Victron SmartShunt, connected via UART connection.  The SmartShunt provides House bank voltage, net current, state of charge, and temperature
  - Battery voltages for the Engine and Thruster banks, gathered by an ADS1115 ADC
  - House load current, as measured by an existing shunt.  The OEM shunt is not inline with the charge sources and some larger loads (e.g. windlass) so it only sees normal house loads (e.g. lights, instrumentation, refrigerator, etc) but it is a good indication of the total charger output, whereas the SmartShunt can only measure what's actually going into the batteries
  - Engine RPM's, measured by counting pulses per second from the engine alternator tachometer output wire.  An optoisolator is used to reliably count the pulses regardless of alternator output voltage
  
At this time one additional remote sensor is used - an Atmega328P based microprocessor reading from a DS18B20 thermometer mounted in the refrigerator.  The Atmega uses an RFM69 radio to send the refrigerator's temperature to the primary Pi for presentation and logging.

The Pi connects via VPN to a home based server running the Grafana presentation web application.  Grafana is configured to pull data from the Pi's InfluxDB database and present dashboards and historical graphs.  Periodically the Pi also sends its measurements to the home based server for storage in a MySQL database.  Additional Grafana dashboards pull from the local MySQL database to present the data when needed.  The MySQL data is less real-time and much lower resolution, but allows the measurements to be viewed when the Pi is out of wifi or cell communication, preventing the Grafana->InfluxDB pulls.  Pi connectivity is provided by a hotspot on the boat and marina wifi.  A script automatically switches to the marina wifi when available to minimize hotspot bandwidth.

<H2>Alternatives</h2>
When I started this project several years ago the Open Source alternatives that now exist weren't built yet, were relatively immature, or I just didn't know about them.  I wanted to build something to meet my needs as closely as possible without unnecessary complications, and I wanted to take the opportunity to learn new things.  Some very capable packages now exist that are worth considering for someone looking for a more out-of-the-box solution.  This list is not intended to be comprehensive, but the alternatives I know about are:
  
  - OpenPlotter, https://openplotter.readthedocs.io/en/3.x.x/.  Openplotter provides a very robust set of capabilities for data logging, presentation, and chartplotting.  It is probably the largest overlap with the capability set that I use, and it includes support for numerous hardware based sensors.
  - Bare Boat Necessities (BBN) OS, https://bareboat-necessities.github.io/.  BBN OS is a very feature rich marine oriented Pi based OS.  My sense it it's too feature rich for the types of data logging and simple presentation I need, but is worth considering for more advanced use cases.
  - Victron Venus OS, https://github.com/victronenergy/venus.  Provided by Victron Energy, Venus OS provides a platform for energy and sensor monitoring and logging similar to what's available on their Cerbo GX hardware devices.  A "large" image is available that adds SignalK and dashboard capabilities.  I've tried Venus OS and found that it would very nearly meet my needs.  Since it is not a standard Raspberry Pi OS getting package support can be more difficult, for example complicating the WireGuard VPN solution I leverage for communication to my home based server.

<H2>Caveats</h2>
I am by no means a professional software developer or electrical engineer.  Though I have a degree in computer science development is not my "day job", so this is just a fun hobby.  I'm sure there are more elegant and reliable ways to design and build this functionality.  I enjoy learning about this kind of technology and blending it with sailing.  I'm presenting it here in case someone is looking for inspiration or examples, but don't rely on it blindly.

<H2>Design Considerations</h2>
Overall, the system is designed to require minimal modification of the boat's existing electrical or physical configuration.  Most interfaces are to existing sensors (e.g. VDO water sensors already on the boat).  Wireless communication is used to minimize wire runs, for example between the electrical hubs in the aft cabin and the main cabin.  Power consumption is minimal, due to the use of an older Pi with lower power requirements (but also less processing power).  Some clear opportunities for design improvement are:
  - A better way to access data from on the boat, particularly when out of cell range.  When in cell range it's possible to connect to the regular Grafana dashboards.  When the boat is out of cell range the home server can only present the MySQL hosted data from before connectivity was lost.  A boat-based dashboard and easy way to access it would be preferable, but would require higher processing power on the Pi for Grafana, and a more easily accessible wifi access point.
  - Reduced hardware, if all data could be gathered from one place
  - More robust charge/load monitoring.  In particular, the ADC reading the load-specific shunt can be overloaded if the ground wire is disconnected between the shunt and the house bank.

<H2>Project index</h2>
The general contents of the project are:
- SRC, containing the source files for the Pi, Pico, and Atmega328p
- Grafana, containing the specification files for the Grafana dashboards
- Diagrams, containing the architecture and data flow diagrams (with a full wiring diagram to follow in the winter when I can re-trace all the connections)
