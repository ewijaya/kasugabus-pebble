"""Train screen settings: the phone codec and the watch parser agree byte for byte."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

NODE = r"""
const extras=require(process.argv[1]+'/src/pkjs/extras');
const out={};
const base=extras.defaults();
out.defaults=extras.encode(base,[]);
out.custom=extras.encode(Object.assign({},base,{trainFlags:7,walkJr:0,walkHankyu:30,buttons:[3,1,4,9]}),[]);
out.roundtrip=extras.decode(out.custom);
out.legacyZero=extras.decode(out.defaults.map((v,i)=>i>=21?0:v));
out.actionCount=extras.ACTION_LABELS.length;
const form=extras.toClay(extras.decode(out.custom));
out.form=form;
const merged=Object.assign({},form,{TrainDirection:'1',TrainDestination:'1',TrainBoth:true,TrainWalkJr:'',TrainWalkHankyu:'9'});
out.fromForm=extras.encode(extras.fromClay(merged,[],base),[]);
function bad(change){try{extras.fromClay(Object.assign({},form,change),[],base);return false;}catch(e){return true;}}
out.rejected=[bad({TrainDirection:'2'}),bad({TrainDestination:'x'}),bad({TrainWalkJr:'31'}),bad({TrainWalkHankyu:'-1'}),bad({TrainBoth:'maybe'})];
function badWire(f){const b=out.defaults.slice();f(b);try{extras.decode(b);return false;}catch(e){return true;}}
out.rejectedWire=[badWire(b=>{b[21]=8;}),badWire(b=>{b[22]=32;}),badWire(b=>{b[23]=32;}),badWire(b=>{b[24]=1;}),badWire(b=>{b[27]=1;})];
console.log(JSON.stringify(out));
"""


class TrainSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = json.loads(subprocess.run(["node", "-e", NODE, str(ROOT)], capture_output=True, text=True, check=True).stdout)

    def test_wire_layout(self):
        defaults = self.result["defaults"]
        self.assertEqual((len(defaults), defaults[21], defaults[22], defaults[23]), (28, 0, 5, 5))
        custom = self.result["custom"]
        self.assertEqual((custom[21], custom[22], custom[23], custom[4]), (7, 1, 31, 9))

    def test_round_trip_and_legacy_records(self):
        decoded = self.result["roundtrip"]
        self.assertEqual((decoded["trainFlags"], decoded["walkJr"], decoded["walkHankyu"]), (7, 0, 30))
        # A record saved before the Train screen has zeros there: default walk.
        legacy = self.result["legacyZero"]
        self.assertEqual((legacy["trainFlags"], legacy["walkJr"], legacy["walkHankyu"]), (0, 4, 4))

    def test_form_maps_choices_to_flags_and_blank_walk_to_default(self):
        form = self.result["form"]
        self.assertEqual((form["TrainDirection"], form["TrainDestination"], form["TrainBoth"], form["TrainWalkJr"], form["TrainWalkHankyu"]),
                         ("1", "1", True, "0", "30"))
        built = self.result["fromForm"]
        self.assertEqual((built[21], built[22], built[23]), (7, 5, 10))

    def test_invalid_input_is_refused(self):
        self.assertTrue(all(self.result["rejected"]))
        self.assertTrue(all(self.result["rejectedWire"]))

    def test_action_list_includes_the_train_action(self):
        self.assertEqual(self.result["actionCount"], 10)

    def test_watch_parser_reads_exactly_what_the_phone_encodes(self):
        with tempfile.TemporaryDirectory(prefix="kasugabus-wire-") as folder:
            executable = Path(folder) / "wire"
            subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", str(ROOT / "src/c/extras.c"),
                            str(ROOT / "tests/extras_wire.c"), "-o", str(executable)], check=True)
            lines = [self.result["defaults"], self.result["custom"], self.result["fromForm"]]
            bad = []
            for index, value in ((21, 8), (22, 32), (23, 32), (24, 1)):
                wire = list(self.result["defaults"])
                wire[index] = value
                bad.append(wire)
            legacy = [v if i < 21 else 0 for i, v in enumerate(self.result["defaults"])]
            text = "\n".join(" ".join(map(str, wire)) for wire in lines + bad + [legacy])
            output = subprocess.run([str(executable)], input=text, capture_output=True, text=True, check=True).stdout.split("\n")[:-1]
        self.assertEqual(output[0], "flags=0 walk_jr=4 walk_hankyu=4 buttons=3,1,4,5 same=1")
        self.assertEqual(output[1], "flags=7 walk_jr=0 walk_hankyu=30 buttons=3,1,4,9 same=1")
        self.assertEqual(output[2], "flags=7 walk_jr=4 walk_hankyu=9 buttons=3,1,4,9 same=1")
        self.assertEqual(output[3:7], ["reject"] * 4)
        # Old records carry zero walk bytes: the watch also reads those as the default 4 minutes.
        self.assertEqual(output[7], "flags=0 walk_jr=4 walk_hankyu=4 buttons=3,1,4,5 same=1")


if __name__ == "__main__":
    unittest.main()
