#  RG9Hydreon2MQTT

Small python script to read the serial port output from the Hydreon RG9 sensor
hooked up to the serial port and send the relevant values to MQTT.

I run it on my Raspberry Pi 4 that also runs indi-allsky

## Systemd Unit installation

```bash
# from the current directory
systemctl --user enable rg9hydreon2mqtt.service

# start it
systemctl --user start rg9hydreon2mqtt

# verify results
systemctl --user status rg9hydreon2mqtt

# this is already done by indi-allsky, but can't hurt to run again 
sudo loginctl enable-linger $USER
```