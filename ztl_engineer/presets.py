"""Task presets for the drop-down: what to tell the model, what to give it, a ready example.

The domains are the ones the ZTL stand has already judged against published worked examples (ztl-stand,
examples/real1..real4): the stand is known to handle each kind of problem, so a preset never promises more than
the stand can prove. `inputs` says which files help: photo (a nameplate, a label), pdf (a datasheet or a manual),
netlist+bom (a schematic tool's SPICE export and its bill of materials), deck (an ANSYS plane-truss deck).
"""

PRESETS = [
    {"id": "any", "title": "Any engineering question", "icon": "🛠️",
     "say": "Describe the device, what it must do and the numbers you know — or ask the AI to propose reasonable "
            "ones. It turns your words into equations, tolerances and requirements, and the stand proves the answer.",
     "give": "Whatever you have: a photo of a label, a datasheet, a sketch with numbers, or just words.",
     "example": "An off-grid cabin has a 600 W solar panel and a 12 V 200 Ah lithium battery that may be discharged "
                "to 20% (80% usable). A 60 W fridge runs 40% of the time. Propose reasonable losses and check that the "
                "battery alone keeps the fridge running through 2 cloudy days, and that one sunny day (4.5 peak sun "
                "hours) refills what those days used.",
     "inputs": ["photo", "pdf"]},
    {"id": "borehole", "title": "Village borehole — enough water from this solar pump?", "icon": "🚰",
     "say": "Say how much water a day is needed, where the water stands in the borehole, how high the tank is and "
            "how many sun hours there are. What nobody measured (how far the water drops while pumping) give as a "
            "range — the stand checks every value in it. Any language.",
     "give": "A photo of the solar pump's nameplate or its datasheet. A second pump can be attached later to compare.",
     "example": "Cette pompe donne-t-elle 8 m³ par jour au village ? L'eau est à 22 m, je ne sais pas de combien "
                "elle baisse en pompant — peut-être 5 à 15 m. Réservoir sur une tour de 6 m. 5 à 6 heures de soleil.",
     "demo": ["nameplate-solar-sp400.png"],
     "next": {"label": "Compare with a stronger pump: its nameplate goes in, and the same question is asked again.",
              "button": "Compare with the second pump (SP-750)", "text": "Et celle-ci ?",
              "demo": ["nameplate-solar-sp750.png"]},
     "note": "Illustrative case with demo nameplates. The pump on the first plate is what a seller would pick from "
             "the resting water level (8 m³ in 5 sun hours at about 30 m) — the check is there to catch that; the "
             "second plate, SP-750, is the one to compare.",
     "inputs": ["photo", "pdf"]},
    {"id": "clinic", "title": "Clinic solar kit — the cheapest that keeps the vaccine fridge on", "icon": "🏥",
     "say": "Say what the clinic must power each day (the vaccine fridge, the lights), how many cloudy days in a row it "
            "must ride through, and the sun hours; ask for the cheapest panel array + battery from the seller's list.",
     "give": "A photo of the seller's price list (panels and batteries with prices).",
     "example": "Our rural clinic runs a vaccine fridge (1.2 kWh a day) and lights (0.5 kWh a day). Which panel array and "
                "battery from this price list is the cheapest pair that keeps them running through two cloudy days in "
                "a row? Sun: 4.5 to 6 hours a day; system losses 15 to 25 %.",
     "demo": ["pricelist-solar-kits.png"],
     "note": "Illustrative case with a demo price list (16 pairs). The stand checks every pair over every tolerance and "
             "proves which one is the cheapest that holds.",
     "inputs": ["photo", "pdf"]},
    {"id": "pump", "title": "Water pump — will it deliver?", "icon": "💧",
     "say": "Say what the pump must do (flow, lift height, pipe length and diameter) and ask whether this pump "
            "does it — or ask what head the pump needs.",
     "give": "A photo of the pump's nameplate or its datasheet PDF with the pump curve.",
     "example": "I need to lift 2 litres per second of water 20 m up through 60 m of 50 mm steel pipe. "
                "Will the pump on this nameplate do it?",
     "demo": ["nameplate-pump.png"],
     "inputs": ["photo", "pdf"]},
    {"id": "dosing", "title": "Dosing pump — chlorine or chemical feed", "icon": "🧪",
     "say": "Give the water flow, the target dose and the chemical's strength; ask whether the pump's range covers it.",
     "give": "The dosing pump's datasheet or label (its min–max output).",
     "example": "A well delivers 30 m³/h and I need 2 mg/L of chlorine from 12.5% sodium hypochlorite "
                "(density 1.2 kg/L). My dosing pump delivers 0.2 to 6 L/h. Can it cover the dose?",
     "inputs": ["photo", "pdf"]},
    {"id": "bearing", "title": "Bearing — will it last?", "icon": "⚙️",
     "say": "Give the load, the speed and the hours it must last; ask which bearing from a list passes.",
     "give": "A bearing catalogue page or datasheet (dynamic load rating Cr).",
     "example": "Radial load 6.5 kN at 1500 rpm, it must last 10 000 hours. The catalogue gives the dynamic "
                "load rating Cr = 40.7 kN for a 6308 and 52.7 kN for a 6309. Which is enough?",
     "inputs": ["photo", "pdf"]},
    {"id": "bolt", "title": "Bolted joint — preload with friction spread", "icon": "🔩",
     "say": "Give the bolt size and grade, the tightening torque and the friction range; ask for the guaranteed "
            "clamp force.",
     "give": "The bolt or fastener datasheet, or a handbook table.",
     "example": "M10x1.5 bolt (pitch diameter 9.026 mm, head bearing mean diameter 13 mm) tightened to 45 N·m; "
                "thread and head friction anywhere from 0.14 to 0.24. Is a clamp force of at least 18 kN guaranteed?",
     "inputs": ["photo", "pdf"]},
    {"id": "oring", "title": "O-ring groove — squeeze and fill", "icon": "⭕",
     "say": "Give the O-ring cross-section and the groove dimensions with tolerances; ask whether squeeze and "
            "fill stay in range.",
     "give": "The O-ring and groove drawing or the seal manufacturer's table.",
     "example": "O-ring 3.53 ±0.10 mm in a groove 2.8 ±0.05 deep and 4.8 wide. Does the squeeze stay between 15 "
                "and 30 % and the fill under 85 %?",
     "inputs": ["photo", "pdf"]},
    {"id": "heatsink", "title": "Heatsink — will the chip stay cool?", "icon": "🔥",
     "say": "Give the power dissipated, the ambient temperature and the limit; ask for the largest heatsink "
            "thermal resistance that still works.",
     "give": "The regulator or transistor datasheet (junction-to-case resistance, max junction temperature).",
     "example": "An LM7805 in TO-220: junction-to-case 5 °C/W, case-to-sink 0.5 °C/W (thermal pad). Input 12 V, "
                "output 5 V, load 1 A. Ambient up to 40 °C, junction at or below 125 °C. What is the largest "
                "heatsink resistance (sink-to-ambient) that still works?",
     "inputs": ["photo", "pdf"]},
    {"id": "regulator", "title": "Voltage regulator — divider tolerance", "icon": "🔌",
     "say": "Give the target output, the reference voltage and the resistor grades; ask whether the output stays "
            "within tolerance.",
     "give": "The regulator datasheet (reference voltage and its tolerance), or your schematic and BOM.",
     "example": "An adjustable regulator with Vref 1.25 V ±1% and 1% resistors must give 3.3 V within ±3%. "
                "Which standard E96 pair works?",
     "inputs": ["pdf", "netlist+bom"]},
    {"id": "circuit", "title": "Circuit from your CAD — SPICE + BOM", "icon": "🧩",
     "say": "Upload the SPICE netlist and the BOM, then say what must hold (a node voltage window, a power limit).",
     "give": "The netlist (.cir) your schematic tool exports and the BOM (.csv) with tolerances.",
     "example": "The ADC input V(adc) must stay between 3.2 and 3.6 V over all tolerances.",
     "demo": ["sensor-divider.cir", "sensor-divider-bom.csv"],
     "inputs": ["netlist+bom"]},
    {"id": "adc", "title": "Amplifier + ADC error budget", "icon": "📈",
     "say": "Give the amplifier's offset and gain errors and the ADC's; ask whether the total stays within budget.",
     "give": "The amplifier and ADC datasheets.",
     "example": "A sensor gives 0–100 mV. A non-inverting op-amp stage with gain 10 (set by two 0.1% resistors, "
                "input offset up to 1 mV) feeds a 12-bit ADC with a 1.25 V reference (±0.1%) and ±2 LSB error. "
                "Is the total error under 1.5% of full scale over the whole input range?",
     "inputs": ["pdf"]},
    {"id": "ntc", "title": "Thermistor — trip temperatures", "icon": "🌡️",
     "say": "Give the NTC part, its divider and the comparator thresholds; ask the guaranteed trip temperatures.",
     "give": "The thermistor datasheet (R25, B value and tolerances).",
     "example": "10k NTC with B=3435 ±1% in a divider with a 10k 1% resistor from 3.3 V; the charger cuts off at "
                "73.5% of the supply. At what temperature does it trip, worst case?",
     "inputs": ["pdf"]},
    {"id": "fiber", "title": "Fiber link — power budget and reach", "icon": "🔦",
     "say": "Give transmitter power, receiver sensitivity, losses per km and per connector; ask the margin or "
            "the longest link.",
     "give": "The transceiver datasheet.",
     "example": "TX −3 to 0 dBm, RX sensitivity −20 dBm, 0.5 dB/km, 4 connectors at 0.5 dB, 3 dB safety margin. "
                "How long can the link be?",
     "inputs": ["pdf"]},
    {"id": "tube", "title": "Tube — allowed pressure", "icon": "🧯",
     "say": "Give the tube size, wall, material and temperature; ask the allowed working pressure.",
     "give": "The tubing catalogue page or material table.",
     "example": "1/2 inch OD 316 stainless tube, 0.049 inch wall (tolerance ±10%), allowable stress 16 700 psi "
                "at 100 °F, Barlow's formula. What working pressure is guaranteed?",
     "inputs": ["photo", "pdf"]},
    {"id": "battery", "title": "Battery — how long will it last?", "icon": "🔋",
     "say": "Give the capacity, the average current and the derating factors; ask the guaranteed lifetime.",
     "give": "The battery datasheet and the board's current measurement or estimate.",
     "example": "CR2032, 225 mAh, average draw 3 µA at 25 °C, capacity derating 15–30%. Is 5 years guaranteed?",
     "inputs": ["photo", "pdf"]},
    {"id": "motor", "title": "Motor + gearhead — conveyor sizing", "icon": "🏭",
     "say": "Give the load, the belt speed and the gear ratio options; ask which motor and ratio work.",
     "give": "The motor and gearhead datasheets.",
     "example": "A conveyor moves 20 kg at 0.2 m/s on a 50 mm diameter drive roller, friction coefficient 0.3. "
                "The motor gives 0.4 N·m at 1500 rpm, gearhead efficiency 0.85. Which of ratios 25, 50 or 100 gives "
                "a belt speed of 0.15–0.25 m/s and enough torque?",
     "inputs": ["pdf"]},
    {"id": "truss", "title": "Truss — deflection from an ANSYS deck", "icon": "🌉",
     "say": "Upload the plane-truss deck and say the modulus tolerance and the deflection limit.",
     "give": "An ANSYS input deck (N, E, MP EX, R, D, F lines).",
     "example": "Steel modulus within ±0.5%. The apex, node 6, must not sag more than 5 mm.",
     "demo": ["roof-truss.txt"],
     "inputs": ["deck"]},
]

# Published worked examples the stand disagrees with — each re-checked from the source's own numbers. The finding is
# not hackathon work (ztl-stand found them in Oct 2026, examples/real1-3); what is new is the app reaching it from
# the plain-words question. The sources are linked, not copied: they are the manufacturers' documents.
PRESETS += [
    {"id": "pub-ti-slva423", "group": "Published examples — check them", "icon": "📄",
     "title": "TI SLVA423 — is ±2.28% really the worst case?",
     "source": "https://www.ti.com/lit/slva423",
     "say": "A manufacturer's application note states a worst-case accuracy. Ask the stand to check it with the "
            "note's own numbers.",
     "give": "The numbers from Section 4 of the note (already in the example), or the PDF itself.",
     "example": "TI application report SLVA423 (2010), Section 4: a TPS79901 regulator with a 1.193 V reference "
                "(device accuracy ±1%) and a feedback divider of two ±1% resistors, R2 = 10 kΩ and R1 = 17.6614 kΩ, "
                "for a 3.3 V rail, Vo = (1 + R1/R2)·Vref. The note says the worst-case total output accuracy is "
                "±2.28%. Check it: does Vo stay within 3.3 V ±2.28% for every combination of tolerances?",
     "inputs": ["pdf"]},
    {"id": "pub-tc1264", "group": "Published examples — check them", "icon": "📄",
     "title": "Microchip TC1264 — is 4.6 V input really safe?",
     "source": "https://www.microchip.com/en-us/product/TC1264",
     "say": "A datasheet's thermal example ends with a maximum input voltage. Ask the stand for the true limit.",
     "give": "The numbers from Section 5.2 of the datasheet (already in the example).",
     "example": "Microchip TC1264 datasheet, Section 5.2: a 2.7 V LDO (output accuracy ±0.5%) in SOT-223 with "
                "θJA = 59 °C/W, load up to 275 mA, ambient up to 95 °C; the junction must stay at or below 125 °C. "
                "Dissipation is (VIN − VOUT)·ILOAD. The datasheet concludes the input may go up to 4.6 V. What is the "
                "largest input voltage that really keeps the junction at or below 125 °C?",
     "inputs": ["pdf"]},
    {"id": "pub-tps25221", "group": "Published examples — check them", "icon": "📄",
     "title": "TI TPS25221 — does 49.9 kΩ guarantee 1 A?",
     "source": "https://www.ti.com/lit/ds/symlink/tps25221.pdf",
     "say": "A datasheet picks a resistor for a guaranteed current limit but leaves out the resistor's own tolerance. "
            "Ask the stand whether the guarantee survives it.",
     "give": "The datasheet's current-limit equation (already in the example).",
     "example": "TI TPS25221 datasheet: the guaranteed minimum current-limit threshold is IOS_min = 56850 / RILIM^1.033 "
                "mA with RILIM in kΩ (valid 20–210 kΩ). The datasheet picks a 49.9 kΩ 1% resistor so that current "
                "limiting never starts below 1000 mA. With the resistor's own ±1% tolerance, is IOS_min ≥ 1000 mA "
                "guaranteed? If not, what is the largest nominal RILIM that guarantees it?",
     "inputs": ["pdf"]},
]

# A heavy run, at the bottom: the stand's own bridge-girder brick (ztl-stand examples/bridge, a pre-existing
# measurement — 755 s on 16 workers, 2026-10-20). It is served from the ztl-stand dependency, not copied here.
PRESETS += [
    {"id": "heavy-bridge", "group": "Heavy — takes minutes", "icon": "🏗️",
     "title": "Bridge girder — 32 768 designs (about 13 min, 16 cores)",
     "say": "A ready problem for the stand: a 36 m Pratt truss girder, 45 bars, 11 deck loads each ±10 %, every "
            "bar's modulus ±0.5 %, five groups of steel sections from a catalogue of 8. Find the lightest design "
            "that meets every stress, buckling and deflection requirement — proved over all tolerances.",
     "give": "Nothing: the example brings the stand's brick file. It runs on several CPU cores; expect minutes.",
     "example": "Find the lightest design of this bridge girder that meets every requirement over all tolerances.",
     "demo": ["stand:examples/bridge/pratt36.json"],
     "note": "Heavy: about 13 minutes with 16 cores (8^5 = 32 768 designs, 91 requirements; measured 760 s). The "
             "progress bar shows the stand's own count of designs decided; it stops early once the lightest design is proved.",
     "inputs": ["brick"]},
    {"id": "heavy-muhanna", "group": "Heavy — takes minutes", "icon": "🗼",
     "title": "Muhanna's cantilever — 2^101 tolerance corners (about 13 min, 4 cores)",
     "say": "A published interval-FEM benchmark (R. Muhanna, IFEM Benchmark 2): a 20-floor one-bay truss cantilever, "
            "101 bars, every bar's modulus ±0.5 %. Ask for the PROVED range of the top corner's displacement — the "
            "exact lowest and highest value over all 2^101 combinations of the tolerances, not a sample.",
     "give": "Nothing: the example brings the truss deck (an ANSYS-style input file).",
     "example": "With every bar's modulus ±0.5 %, what is the proved range of node 42's horizontal and vertical "
                "displacement?",
     "demo": ["stand:examples/truss/cantilever20.txt"],
     "note": "Heavy: 11–13 minutes (measured 635 s and 758 s). Each end of each range is its own proof — three stand runs "
             "of about 3 minutes each, which do not split further — so the four ends run side by side on 4 cores. "
             "The answer is the exact range: both ends are attained by a real corner and proved not to be exceeded.",
     "inputs": ["deck"]},
]

# the drop-down's groups: "Any" stays first and alone; the simple tasks in their own group (curator, 26.10)
for _p in PRESETS:
    if _p["id"] != "any" and not _p.get("group"):
        _p["group"] = "Simple tasks"


def by_id(pid: str) -> dict:
    for p in PRESETS:
        if p["id"] == pid:
            return p
    return PRESETS[0]          # "Any engineering question", the app's default (curator, 27.10)
