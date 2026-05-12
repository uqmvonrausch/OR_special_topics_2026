from ortools.sat.python import cp_model
import json

with open("./data/scenario_1.json") as data_file:
    data = json.load(data_file)

MINS_PER_HOUR = 60

S = range(len(data["shovels"]))
D = range(len(data["dumps"]))
T = range(data["n_trucks"])

def calc_job_duration(start_shovel_idx: int, dump_idx: int, end_shovel_idx: int):
    
    loaded_distance_m = data["distance_matrix"][start_shovel_idx][dump_idx]
    loaded_drive_time_min = (loaded_distance_m / data["speed_loaded_kph"]) * MINS_PER_HOUR / 1000

    unloaded_distance_m = data["distance_matrix"][end_shovel_idx][dump_idx]
    unloaded_drive_time_min = (unloaded_distance_m / data["speed_unloaded_kph"]) * MINS_PER_HOUR / 1000

    return data["loading_time_min"] + loaded_drive_time_min + \
        data["unloading_time_min"] + unloaded_drive_time_min

Jobs = {(s,d,ss) : calc_job_duration(s, d, ss)
        for s in S for d in D for ss in S}

CP = cp_model.CpModel()


