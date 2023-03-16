from openai.embeddings_utils import (
    get_embedding,
    cosine_similarity,
    distances_from_embeddings,
    tsne_components_from_embeddings,
    chart_from_components,
    indices_of_nearest_neighbors_from_distances,
)
import pandas as pd
import pickle
import os

import openai
import re
from flask import Flask, redirect, render_template, request, url_for
import cv2
from flask import Flask
from flask import request
import os
import base64
from WindowStructure import *
import time
from NodeDescriberManager import *
import json
import numpy as np
from flask_socketio import SocketIO
from flask import Flask
from flask_sockets import Sockets
import datetime


app = Flask(__name__)

openai.api_key = "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"
layout = None
screenshot = None
imgdata = None
cnt = 0
semantic_nodes = []
describermanagers = {}

i = 0
prompt_now = ""
intention = ""
intent_embedding = None
html_detect = False
agenda_detect = False
upload_time = None
time_between_upload = 1
all_text = ""  # 当前页面的所有文本
describermanagers_init = False
page_root = None
semantic_info = []
current_path = []
current_path_str = "Begin"

chart_data={
        "labels": [],
        "datasets": [
            {
                "data": [],
                "backgroundColor": [
                    "rgb(255, 99, 132)",
                    "rgb(54, 162, 235)",
                    "rgb(255, 205, 86)",
                    "rgb(75, 192, 192)",
                    "rgb(153, 102, 255)",
                ],
                "hoverOffset": 4,
            },
        ],
    }
EMBEDDING_MODEL = "text-embedding-ada-002"

embedding_cache_path = "embeddings_cache.pkl"

# load the cache if it exists, and save a copy to disk
try:
    embedding_cache = pd.read_pickle(embedding_cache_path)
except FileNotFoundError:
    embedding_cache = {}
with open(embedding_cache_path, "wb") as embedding_cache_file:
    pickle.dump(embedding_cache, embedding_cache_file)

# define a function to retrieve embeddings from the cache if present, and otherwise request via the API


def embedding_from_string(
    string: str,
    model: str = EMBEDDING_MODEL,
    embedding_cache=embedding_cache
) -> list:
    """Return embedding of given string, using a cache to avoid recomputing."""
    if (string, model) not in embedding_cache.keys():
        embedding_cache[(string, model)] = get_embedding(string, model)
        with open(embedding_cache_path, "wb") as embedding_cache_file:
            pickle.dump(embedding_cache, embedding_cache_file)
    return embedding_cache[(string, model)]


@app.route('/detect', methods=['GET'])
def detect():
    global html_detect, all_text
    print("detect")
    detect_money()
    while True:
        if time.time()-upload_time <= time_between_upload:
            continue
        else:
            html = detect_html(all_text)
            if html:
                return {"type": "html", "html": str(html)}
            else:
                continue


def init_describer():
    print("loadmodel")
    global relation_dict
    with open('./static/data'+'/manager_structure.json', 'r', encoding='utf-8') as file:
        describermanagers_str = json.load(file)
        global describermanagers
        for key, value in describermanagers_str.items():
            value = json.loads(value)
            print("loading", key)
            if key == "Root Object;":
                describermanagers[key] = NodeDescriberManager(
                    "Root", None, "Root Object;")
            if key.count(";") > 1:
                p_last = key.split(";")[-2]
                model_fa_id = key.replace(p_last+";", "")
                describermanagers[key] = NodeDescriberManager(
                    value["type"], describermanagers[model_fa_id], key)
                describermanagers[model_fa_id].update_children(
                    describermanagers[key])
                tmp_positive_ref_nodes = []
                tmp_negative_ref_nodes = []
                tmp_positive_nodes = []
                for node_info in value["positive_ref"]:
                    with open('static/data/'+'page' + str(node_info["page_id"]) + '.json', 'r')as fp:
                        tmp_layout = json.loads(fp.read())
                    tmp_page_instance = PageInstance()
                    if isinstance(tmp_layout, list):
                        tmp_layout = tmp_layout[0]
                    tmp_page_instance.load_from_dict("", tmp_layout)
                    tmp_page_root = tmp_page_instance.ui_root
                    tmp_node = tmp_page_root.get_node_by_relative_id(
                        node_info["index"])
                    tmp_node.update_page_id(node_info["page_id"])
                    tmp_positive_ref_nodes.append(
                        (tmp_node.findBlockNode(), tmp_node))
                for node_info in value["negative_ref"]:
                    print("node_info", node_info)
                    with open('static/data/'+'page' + str(node_info["page_id"]) + '.json', 'r')as fp:
                        tmp_layout = json.loads(fp.read())
                    tmp_page_instance = PageInstance()
                    if isinstance(tmp_layout, list):
                        tmp_layout = tmp_layout[0]
                    tmp_page_instance.load_from_dict("", tmp_layout)
                    tmp_page_root = tmp_page_instance.ui_root
                    print(node_info["page_id"],
                          tmp_page_root.generate_all_text())
                    tmp_node = tmp_page_root.get_node_by_relative_id(
                        node_info["index"])
                    tmp_node.update_page_id(node_info["page_id"])
                    tmp_negative_ref_nodes.append(
                        (tmp_node.findBlockNode(), tmp_node))
                for node_info in value["positive"]:
                    with open('static/data/'+'page' + str(node_info["page_id"]) + '.json', 'r')as fp:
                        tmp_layout = json.loads(fp.read())
                    tmp_page_instance = PageInstance()
                    if isinstance(tmp_layout, list):
                        tmp_layout = tmp_layout[0]
                    tmp_page_instance.load_from_dict("", tmp_layout)
                    tmp_page_root = tmp_page_instance.ui_root
                    tmp_node = tmp_page_root.get_node_by_relative_id(
                        node_info["index"])
                    tmp_node.update_page_id(node_info["page_id"])
                    tmp_positive_nodes.append(
                        (tmp_node.findBlockNode(), tmp_node))
                describermanagers[key].update(
                    tmp_positive_ref_nodes, tmp_negative_ref_nodes, tmp_positive_nodes)
    global describermanagers_init
    describermanagers_init = True
    # with open('./static/data/'+'/relation_dict.json', 'r', encoding='utf-8') as file:
    #     relation_dict = json.loads(file.read())
    # with open('./static/data/'+'/model_structure.json', 'r', encoding='utf-8') as file:
    #     model_data = json.loads(file.read())
    #     print(model_data)
    #     return model_data


@app.route('/demo', methods=['POST'])
def demo():
    if not describermanagers_init:
        init_describer()
    global html_detect
    html_detect = True
    global cnt
    cnt += 1
    global layout,  screenshot, imgdata, img_np, page_instance, pageindex, page_id_now, page_root, semantic_nodes, semantic_info
    start_time = time.time()
    page_id_now = cnt
    screenshot = request.form["screenshot"]
    layout = request.form['layout']
    # pageindex = request.form['pageindex']
    imgdata = base64.b64decode(screenshot)
    nparr = np.frombuffer(imgdata, np.uint8)
    img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    result_json = {"state": "ok"}
    fp = open('static/data/imagedata' + str(cnt) +
              ".jpg", 'wb')  # 'wb'表示写二进制文件
    fp.write(imgdata)
    fp.close()
    fp = open('static/data/page' + str(cnt) + ".json", 'w')
    fp.write(layout)
    fp.close()
    page_instance = PageInstance()
    page_instance.load_from_dict("", json.loads(layout))
    print("page loaded")
    page_root = page_instance.ui_root
    if len(page_root.children.children.children) == 2:
        print("FUCK")
        page_root.children.children.children = page_root.children.children.children[0]
    global all_text, semantic_info, describermanagers
    all_text = page_root.generate_all_text()
    print("all_text", all_text)
    semantic_nodes = page_root.get_all_semantic_nodes()

    # 创建与semantic_nodes["nodes"]等长的type列表，用于存放每个节点的类型
    # semantic_nodes["type"] = ["" for ii in range(len(semantic_nodes["nodes"]))]
    # for i in range(len(semantic_nodes["nodes"])):
    #     semantic_nodes["nodes"][i].update_page_id(page_id_now)
    #     dis = 99.0
    #     for key, value in describermanagers.items():
    #         if key == "Root Object;":
    #             continue
    #         tmp_dis = value.calculate(semantic_nodes["nodes"][i])
    #         if tmp_dis < dis:
    #             dis = tmp_dis
    #             semantic_nodes["type"][i] = key.split(";")[-2]
    # print("semantic_nodes", semantic_nodes["type"])

    semantic_info = [node.generate_all_semantic_info()
                     for node in semantic_nodes["nodes"]]

    for i in range(len(semantic_info)):
        semantic_info[i] = "{"+",".join([str(i) for i in semantic_info[i]["Major_text"]])+"}-{"+",".join([str(i) for i in semantic_info[i]["text"]])+"}-{"+",".join(
            [str(i) for i in semantic_info[i]["content-desc"]])+"}-{"+",".join(
            [str(i) for i in semantic_info[i]["class"]])+"}"
    print("semantic info,", semantic_info)
    print("semantic_nodes", len(semantic_nodes))
    end_time = time.time()
    global upload_time  # 上一次上传的时间
    upload_time = end_time  # 记录本次上传的时间
    print("upload_time", upload_time)
    print("time:", end_time-start_time, flush=True)
    result_json["time"] = (end_time-start_time)*1000
    return json.dumps(result_json)


@app.route("/", methods=("GET", "POST"))
def index():
    global i, seq, ins_seq,  prompt_now, intention, intent_embedding
    print(request.form)
    global semantic_info, current_path, current_path_str,chart_data
    if request.method == "POST" and "intention" in request.form:

        intention = request.form["intention"]
        initialize_prompt(intention)
        intent_embedding = embedding_from_string(intention)
        print(prompt_now)
        print(semantic_info)
    elif request.method == "POST" and "reset" in request.form:
        if intention != "":
            initialize_prompt(intention)
            i = 0
            current_path = []
            current_path_str = "Begin"
    elif request.method == "POST" and "next" in request.form:

        img_id = str(cnt)
        print(semantic_info)
        possible_comp_str = [i.split("{")[1].split("}")[
            0] for i in semantic_info if i.split("{")[1].split("}")[0] != ""]
        print(possible_comp_str)
        embeddings = [embedding_from_string(string)
                      for string in possible_comp_str]
        similarity = [cosine_similarity(
            intent_embedding, embedding) for embedding in embeddings]
        print(similarity)

        semantic_info = str(semantic_info)[2:-2].replace(r"}, {", " ,")
        print(semantic_info)
        if len(prompt_now) > 10:
            prompt_now.pop(-2)
        print(generate_prompt(semantic_info=str(semantic_info)))
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=prompt_now,
            temperature=0,
        )
        print(response)
        result = response['choices'][0]['message']['content']
        prompt_now.append(response['choices'][0]['message'])
        # 找到<SOC><EOC>之间的内容
        comp_selected = result[result.find("<SOC>")+5:result.find("<EOC>")]
        current_path.append(comp_selected)
        current_path_str = "-".join(current_path)
        print("current_path", current_path_str)
        print(result)
        return render_template("index.html", result=result, img_id=img_id, semantic_info=semantic_info,chart_data=chart_data)
    return render_template("index.html", chart_data=chart_data)


def generate_prompt(semantic_info):
    global prompt_now, i
    prompt_now.append({"role": "user",
                       "content": """{},Current components:"{}".""".format(i+1, semantic_info)})
    i += 1
    return prompt_now


def initialize_prompt(init):
    global prompt_now
    prompt_now = [
        {"role": "system",
         "content": """You are an assistant translating user's intention to UI actions.
         Rules:
         1,UI components are organized as {major text}-{all text}-{description}-{android class}.
         2,Please strictly follow the answer format:"Expecting...Currently".
         3,Only one short instruction is allowed to be generated per step.
         4,Each instruction can only chooes from the components of the current page!"""},
        {"role": "user",
         "content": """A user's intention is to 'Turn off Dark mode in WeChat'."""},
        {"role": "user",
         "content": """1,Current page components:"['{Settings}-{}-{}-{LinearLayout}', '{Sticker Gallery}-{}-{}-{LinearLayout}', '{My Posts}-{}-{}-{LinearLayout}', '{Favorites}-{}-{}-{LinearLayout}', '{Services}-{}-{}-{LinearLayout}']"""},
        {"role": "assistant",
         "content": """The current page is:"Me page".Expecting the next page to appear :['{General}-{}-{}-{LinearLayout}'].Currently the instruction should be :[Click on <SOC>Settings<EOC> ]."""},
        {"role": "user",
         "content": """2,Current page components:"['{My Information & Authorizations}-{}-{}-{LinearLayout}', "{Friends' Permissions}-{}-{}-{LinearLayout}", '{Privacy}-{}-{}-{LinearLayout}', '{General}-{}-{}-{LinearLayout}', '{Chats}-{}-{}-{LinearLayout}', '{}-{}-{Back}-{LinearLayout}']"."""},
        {"role": "assistant",
         "content": """The current page is:"Settings page".Expecting the next page to appear :['{Dark Mode}-{}-{}-{LinearLayout}'].Currently the instruction should be :[Click on <SOC>General<EOC> ]."""},
        {"role": "user",
         "content": """3,Current page components:"['{Manage Discover}-{}-{}-{LinearLayout}', '{Photos, Videos, Files & Calls}-{}-{}-{LinearLayout}', '{Text Size}-{}-{}-{LinearLayout}','{Dark Mode}-{Auto}-{}-{LinearLayout}', '{}-{}-{Back}-{LinearLayout}']"."""},
        {"role": "assistant",
         "content": """The current page is:"Settings-General subpage".Expecting the next page to appear :["DONE!"].Currently the instruction should be :[Click on <SOC>Dark Mode<EOC> ].The Task is DONE!"""},
    ]
    prompt_now.append(
        {"role": "user", "content": """A user's intention is to '{}'.""".format(init)})


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
