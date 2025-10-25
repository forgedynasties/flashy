### List qcom devices devices
```bash
lsusb -v | grep -A2 "Qualcomm"
Bus 001 Device 024: ID 05c6:9008 Qualcomm, Inc. Gobi Wireless Modem (QDL mode)
Bus 001 Device 025: ID 01c6:9008 Qualcomm, Inc. Gobi Wireless Modem (QDL mode)

```
### Flash firmware to the qcom device
```bash
sudo qdl -d --storage emmc prog_firehose_ddr.elf rawprogram_unsparse0.xml patch0.xml
```
Note: This command will randomly flash to one out of all the qcom devices connect in edl mode.

### Flash to a specific device
To flash the firmware to a specific device we need to get its serial first.
```bash
lsusb | grep Qualcomm

Bus 001 Device 051: ID 05c6:9008 Qualcomm, Inc. Gobi Wireless Modem (QDL mode)

Bus 001 Device 041: ID 13fa:9008 Qualcomm, Inc. Gobi Wireless Modem (QDL mode)
```

plug the ID "05c6:9008" in the following command
```bash
lsusb -v -d 05c6:9008 2>/dev/null | grep iProduct | awk -F'SN:' '{print $2}'

CB4713E8
```

```bash
sudo qdl -d -s CB4713E8 --storage emmc prog_firehose_ddr.elf rawprogram_unsparse0.xml patch0.xml
```

