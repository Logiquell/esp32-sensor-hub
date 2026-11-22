# Picks which app runs at power-up. Change APP and re-upload this file.
#   'hub'   - all three modes, MODE button (GPIO4) cycles RADAR/TILT/CLIMATE
#   'tilt'  - bubble level on the OLED (ADXL345)
#   'radar' - ultrasonic radar on servo (HC-SR04), OLED + PC display
APP = 'hub'

__import__(APP)
