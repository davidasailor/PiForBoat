# Todo List: Aft Cabin Pico Firmware Updates

This todo list outlines the necessary firmware modifications for the Raspberry Pi Pico (`src/pico/code.py` and `src/pico/lib/Vedirect.py`) to fix UART stability, infinite loops, and crash hazards. 

---

## Task 1: Fix Infinite Loop in `Vedirect.py`
In [Vedirect.py](file:///mnt/server/Documents/Boat/PiForBoatPy/PiForBoatPy/src/pico/lib/Vedirect.py), the `read_data_single()` method has a `while True:` loop. If a message block has an invalid checksum, the parser gets stuck reprocessing the same bytes forever, locking up the Pico sender.

### Proposed Changes to `src/pico/lib/Vedirect.py`:
Change [Vedirect.py:L68-74](file:///mnt/server/Documents/Boat/PiForBoatPy/PiForBoatPy/src/pico/lib/Vedirect.py#L68-74):

```diff
-    def read_data_single(self, message):
-        while True:
-            for data in message:
-                packet = self.input(data)
-                if (packet != None):
-                    return packet
+    def read_data_single(self, message):
+        for data in message:
+            packet = self.input(data)
+            if (packet != None):
+                return packet
+        return None
```

---

## Task 2: Validate Shunt Checksum in `pico/code.py`
With the above fix, `read_data_single()` can now return `None` if the serial data checksum check fails. In [pico/code.py](file:///mnt/server/Documents/Boat/PiForBoatPy/PiForBoatPy/src/pico/code.py), we must check for this `None` return and raise a `ValueError` to fall back to the safe defaults.

### Proposed Changes to `src/pico/code.py`:
Change [pico/code.py:L130-136](file:///mnt/server/Documents/Boat/PiForBoatPy/PiForBoatPy/src/pico/code.py#L130-136):

```diff
     # Read a VE_Direct packet from UART
     try:
         if(SHUNT):
             ve_values = read_ve()
+            if ve_values is None:
+                raise ValueError("Invalid shunt checksum")
         a=1
-
     except BaseException as e:
         log("Failed to read VE_Direct; Using defaults; error was: " + str(e))
```

And in `read_ve()`, check for `None` from the parser:
```diff
     keys = shunt.read_data_single(data) # Uses auxiliary function from serial VEDirect library
+    if keys is None:
+        return None
 
     values = {
```

---

## Task 3: Enable Signed Temperature Encoding in `pico/code.py`
If a temperature sensor goes below 0°C (32°F) or returns a negative error code/reading, the unsigned `to_bytes(2, "big")` will raise an `OverflowError` and crash the Pico. The Pi receiver already expects signed integers for temperatures, so we must add `signed=True` to the serialization.

### Proposed Changes to `src/pico/code.py`:
Change [pico/code.py:L160-161](file:///mnt/server/Documents/Boat/PiForBoatPy/PiForBoatPy/src/pico/code.py#L160-161):

```diff
-    temp1_bytes = round(temp1*10).to_bytes(2, "big")
-    temp2_bytes = round(temp2*10).to_bytes(2, "big")
+    temp1_bytes = round(temp1*10).to_bytes(2, "big", signed=True)
+    temp2_bytes = round(temp2*10).to_bytes(2, "big", signed=True)
```
