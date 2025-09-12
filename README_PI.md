# Raspberry Pi Optimized Bike Monitor

This version of the bike monitoring system is specifically optimized for Raspberry Pi devices with limited CPU, memory, and storage resources.

## 🍓 Pi Optimizations

### Memory & CPU Optimizations
- **Reduced page counts**: 1-3 pages instead of 5-15
- **Smaller buffer sizes**: 150-200 bikes instead of 400-450
- **Memory-optimized browser**: Single process, disabled images/JS
- **Automatic browser restart**: Every 2 pages to free memory
- **Longer intervals**: 10+ minutes between checks

### Browser Optimizations
- **Disabled JavaScript**: Faster page loading
- **Disabled images**: Saves bandwidth and memory
- **Single process mode**: Reduces memory usage
- **Aggressive timeouts**: Faster failure detection
- **Resource blocking**: Blocks unnecessary content

### Timing Optimizations
- **Longer base intervals**: 10 minutes instead of 5
- **Extended delays**: 15 seconds between monitors
- **Reduced concurrent operations**: Single-threaded buffer init

## 🚀 Quick Start

### 1. Setup
```bash
# Run the Pi setup script
./setup_raspberry_pi.sh

# Activate virtual environment
source .venv/bin/activate
```

### 2. Configuration
Use the Pi-optimized config files:
- `configs/config-2dehands-pi.json`
- `configs/config-2dehands-sportfietsen-pi.json`
- `configs/config-marktplaats-pi.json`
- `configs/centralized-config-pi.json`

### 3. Run
```bash
# Run with Pi-optimized settings
python run_monitors_pi.py configs/

# Or run specific configs
python run_monitors_pi.py configs/config-2dehands-pi.json
```

## 📊 Performance Comparison

| Setting | Standard | Pi Optimized |
|---------|----------|--------------|
| Pages per check | 5-15 | 1-3 |
| Buffer size | 400-450 | 150-200 |
| Check interval | 5 min | 10+ min |
| Memory usage | ~200MB | ~100MB |
| CPU usage | High | Low |
| Browser restart | Never | Every 2 pages |

## ⚙️ Configuration Files

### Pi-Optimized Configs
All Pi configs include:
```json
{
  "pi_optimized": true,
  "request_delay": 2.0,
  "max_bikes": 150,
  "initial_pages": 2,
  "ongoing_pages": 1
}
```

### Centralized Timing (Pi)
```json
{
  "centralized_timing": {
    "base_interval": 600,
    "time_based_intervals": {
      "01:00-07:00": 1800,
      "07:00-16:00": 900,
      "16:00-22:00": 600,
      "22:00-01:00": 900
    }
  }
}
```

## 🔧 Customization

### Adjust for Your Pi
Edit `configs/centralized-config-pi.json`:

```json
{
  "pi_optimizations": {
    "max_pages_per_monitor": 1,    // Reduce to 1 for very slow Pi
    "request_delay": 3.0,          // Increase for slower network
    "page_timeout": 20000,         // Increase for slower Pi
    "max_pages_per_session": 1     // Restart browser more often
  }
}
```

### Memory Monitoring
Monitor memory usage:
```bash
# Check memory usage
free -h

# Monitor during scraping
watch -n 1 'free -h && ps aux | grep python'
```

## 🐛 Troubleshooting

### Out of Memory
- Reduce `max_pages_per_monitor` to 1
- Reduce `max_bikes` to 100
- Increase `max_pages_per_session` to 1

### Slow Performance
- Increase `request_delay` to 3.0+
- Increase `base_interval` to 900+ seconds
- Reduce `ongoing_pages` to 1

### Browser Crashes
- Increase `page_timeout` to 30000
- Reduce `max_pages_per_session` to 1
- Check available memory: `free -h`

## 📈 Monitoring

### System Resources
```bash
# CPU and memory usage
htop

# Disk usage
df -h

# Network usage
iftop
```

### Log Monitoring
```bash
# Follow logs
tail -f 2dehands_pi.log

# Check for errors
grep ERROR *.log
```

## 🔄 Service Installation

### Systemd Service
```bash
# Install service
sudo cp bike-monitor-pi.service /etc/systemd/system/
sudo systemctl enable bike-monitor-pi
sudo systemctl start bike-monitor-pi

# Check status
sudo systemctl status bike-monitor-pi

# View logs
sudo journalctl -u bike-monitor-pi -f
```

## 📝 Notes

- **Pi 4 recommended**: Pi 3 may struggle with browser operations
- **SD card speed**: Use a fast SD card (Class 10+)
- **Power supply**: Use official Pi power supply
- **Cooling**: Ensure adequate cooling for sustained operation
- **Network**: Stable internet connection required

## 🆚 Standard vs Pi

| Feature | Standard | Pi Optimized |
|---------|----------|--------------|
| Scraping speed | Fast | Slower but stable |
| Resource usage | High | Low |
| Reliability | Good | Excellent |
| Maintenance | Low | Very low |
| Cost | Higher | Lower |

The Pi-optimized version trades speed for stability and resource efficiency, making it perfect for 24/7 operation on low-power devices.
