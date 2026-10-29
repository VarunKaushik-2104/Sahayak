import json,sys
M={
"6":{"Maths":[
("Patterns in Mathematics",["m6_alg"]),("Lines and Angles",["m6_geo"]),("Number Play",["m6_num"]),("Prime Time",["m6_num"]),
("Perimeter and Area",["m6_mens"]),("Fractions",["m6_frac"]),("Playing with Constructions",["m6_geo"]),("The Other Side of Zero",["m6_int"])],
"Science":[
("Diversity in the Living World",["s6_plant"]),("Mindful Eating: A Path to a Healthy Body",["s6_food"]),("Measurement of Length and Motion",["s6_motion"]),
("Materials Around Us",["s6_mat"]),("Temperature and its Measurement",["s7_heat"]),("Methods of Separation in Everyday Life",["s6_sep"])]},
"7":{"Maths":[
("A Peek Beyond the Point",["m7_frac"]),("Expressions Using Letter Numbers",["m7_expr"]),("A Tale of Three Intersecting Lines",["m7_tri"]),
("Working with Fractions",["m7_frac"]),("Geometric Twins",["m7_tri"]),("Operations with Integers",["m7_int"]),
("Finding Common Ground",["m6_num"]),("Another Peek Beyond the Point",["m7_frac"]),("Finding the Unknown",["m7_eq","m8_lin"])],
"Science":[
("Exploring Substances: Acidic, Basic, and Neutral",["s7_acid"]),("Electricity: Circuits and their Components",["s6_elec","s7_elec"]),
("The World of Metals and Non-metals",["s8_metal"]),("Changes Around Us: Physical and Chemical",["s7_chem"]),
("Adolescence: A Stage of Growth and Change",["s8_repro"]),("Heat Transfer in Nature",["s7_heat"]),("Measurement of Time and Motion",["s7_motion"]),
("Life Processes in Animals",["s7_nutr"]),("Life Processes in Plants",["s7_nutr","s6_plant"]),("Light: Shadows and Reflections",["s7_light","s6_light"])]},
"8":{"Maths":[
("A Square and a Cube",["m8_sq"]),("Power Play",["m8_exp"]),("Quadrilaterals",["m8_quad"]),("We Distribute, Yet Things Multiply",["m8_alg"]),
("Proportional Reasoning-1",["m7_ratio","m6_ratio"]),("Fractions in Disguise",["m8_pct","m7_ratio"]),("Proportional Reasoning-2",["m7_ratio"]),
("Tales by Dots and Lines",["m8_data"]),("Area",["m8_mens","m7_mens"])],
"Science":[
("The Invisible Living World: Beyond Our Naked Eye",["s8_cell"]),("Electricity: Magnetic and Heating Effects",["s7_elec"]),
("Exploring Forces",["s8_force"]),("Pressure, Winds, Storms, and Cyclones",["s8_force"]),("Particulate Nature of Matter",["s9_matter"]),
("Nature of Matter: Elements, Compounds, and Mixtures",["s9_atom"]),("Light: Mirrors and Lenses",["s8_light"])]},
"9":{"Maths":[
("Orienting Yourself: The Use of Coordinates",["m9_coord"]),("Introduction to Linear Polynomials",["m9_poly"]),("The World of Numbers",["m9_num"]),
("Exploring Algebraic Identities",["m9_poly","m8_alg"]),("The Mathematics of Maybe: Introduction to Probability",["m9_stat"]),
("How Quantities Combine: Understanding Data",["m9_stat"]),("Two Variables, One Line",["m9_lin2"]),("Math of Space: Surface Area and Volume",["m9_mens"]),
("Predicting What Comes Next: Exploring Sequences and Progressions",["m10_ap"])],
"Science":[
("Cell: The Building Block of Life",["s9_cell"]),("Tissues in Action",["s9_cell"]),("Describing Motion Around Us",["s9_motion"]),
("Exploring Mixtures and their Separation",["s9_matter"]),("How Forces Affect Motion",["s9_force"]),("Work, Energy, and Simple Machines",["s9_work"]),
("Journey Inside the Atom",["s9_atom"]),("Atomic Foundations of Matter",["s9_atom"]),("Sound Waves: Characteristics and Applications",["s9_sound","s8_sound"])]},
"10":{"Maths":[
("Real Numbers",["m9_num"]),("Polynomials",["m9_poly"]),("Pair of Linear Equations in Two Variables",["m10_pair"]),("Quadratic Equations",["m10_quad"]),
("Arithmetic Progressions",["m10_ap"]),("Triangles",["m10_simtri"]),("Introduction to Trigonometry",["m10_trig"]),
("Surface Areas and Volumes",["m10_mens"]),("Statistics",["m10_prob"]),("Probability",["m10_prob"])],
"Science":[
("Chemical Reactions and Equations",["s10_chem"]),("Acids, Bases and Salts",["s10_acid"]),("Metals and Non-metals",["s10_metal"]),
("Carbon and its Compounds",["s10_carbon"]),("Life Processes",["s10_life"]),("How do Organisms Reproduce?",["s8_repro"]),
("Heredity and Evolution",["s10_heredity"]),("Light – Reflection and Refraction",["s10_light"]),("Human Eye and Colourful World",["s10_light","s8_light"]),
("Electricity",["s10_elec"])]},
}
base="/tmp/claude-0/-home-claude/f8bb6f52-0b56-5b6e-b8bb-28bd236a4d28/scratchpad/s2/"
sk={t['id']:t for t in json.load(open(base+"skeleton.json"))}
out={"board":"CBSE","book":"NCERT","classes":{}}
used=set()
for c,subs in M.items():
    out["classes"][c]={}
    for s,L in subs.items():
        out["classes"][c][s]=[]
        for n,tp in L:
            for t in tp:
                assert t in sk,t
                used.add(t)
            out["classes"][c][s].append({"name":n,"topics":tp,"verified":True})
json.dump(out,open(base+"map/CBSE.json","w"),indent=1,ensure_ascii=False)
print([t for t in sk if t not in used])
for c in M:
    print(c,{s:len(v) for s,v in M[c].items()})
