# inventree-ptouch

InvenTree label printer driver for Brother P-touch printers over Bluetooth
(RFCOMM). Detects the loaded tape and renders the label template to fit it.

Models: PT-E560BT (tested), PT-E310BT, PT-P710BT, PT-D460BT, PT-D610BT,
PT-E720BT, PT-P300BT (untested).

## Use

1. Pair the printer with the InvenTree server (`bluetoothctl`).
2. `pip install .` into InvenTree's environment, restart InvenTree.
3. Add a label printer machine with driver *Brother P-touch (Bluetooth)* and
   the printer's Bluetooth address.
4. Upload `inventree_ptouch/templates/ptouch_part_label.html` as a part label
   template and `ptouch_location_label.html` as a stock location label
   template, each with metadata `{"ptouch_auto_height": true}`.

`deploy/` has optional scripts that automate steps 2-4 over SSH.

## Tests

    pip install pytest pillow && python -m pytest -q

## License

GPL-3.0-or-later, see `LICENSE`.
