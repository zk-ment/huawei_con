import numpy as np
from model_service.tfserving_model_service import TfServingBaseService
import pandas as pd
from get_road_point import get_road_point, get_kv_point2prop

class mnist_service(TfServingBaseService):

    def _preprocess(self, data):

        names = ["Cell Index", "Cell X", "Cell Y", "Height", "Azimuth", "Electrical Downtilt",
                 "Mechanical Downtilt", "Frequency Band", "RS Power", "Cell Altitude",
                 "Cell Building Height", "Cell Clutter Index", "X", "Y",
                 "Altitude", "Building Height", "Clutter Index"]
        index_weight = [0.0, 0.0, 93.5, 0.0, 0.0, 94.5, 93.5, 95.5, 96.5, 0.0,
                        94.5, 96.5, 95.5, 95.5, 95.5, 95.5, 99.7, 94.3, 92.85, 0.0]

        index_names = ["oceans", "lakes", "wetlands", "suburban open areas", "urban open areas",
                       "road open areas", "vegetation", "shrub", "forest", "super-high buildings",
                       "high buildings", "mid buildings", "density buildings", "buildings",
                       "sparse industrial", "density", "suburban", "developed suburban", "rural", "CBD"]
        df_data = pd.DataFrame(columns=names)
        preprocessed_data = {}
        filesDatas = []
        for k, v in data.items():
            for file_name, file_content in v.items():
                pb_data = pd.read_csv(file_content)
                df_data = pd.concat([df_data, pb_data], ignore_index=True)
                # input_data = np.array(pb_data.get_values()[:,0:17], dtype=np.float32)
                # print(file_name, input_data.shape)
                # filesDatas.exend(input_data)

        station_X = np.array(df_data["Cell X"], dtype=np.float64)
        station_Y = np.array(df_data["Cell Y"], dtype=np.float64)
        mobile_X = np.array(df_data["X"], dtype=np.float64)
        mobile_Y = np.array(df_data["Y"], dtype=np.float64)
        theta_AZ = np.array(df_data["Azimuth"], dtype=np.float64)

        station_AH = np.array(df_data["Cell Altitude"], dtype=np.float32)
        station_BH = np.array(df_data["Height"], dtype=np.float32)
        mobile_AH = np.array(df_data["Altitude"], dtype=np.float32)
        mobile_BH = np.array(df_data["Building Height"], dtype=np.float32)

        theta_A = df_data["Electrical Downtilt"].astype(float)
        theta_B = df_data["Mechanical Downtilt"].astype(float)

        station_Index = df_data["Cell Clutter Index"].astype(int)
        mobile_Iindex = df_data["Clutter Index"].astype(int)

        delat_X = mobile_X - station_X

        theta = np.arctan((mobile_Y - station_Y) / (mobile_X - station_Y)) * 180 / np.pi
        theta *= -1
        theta[delat_X > 0] += 90
        theta[delat_X < 0] += 270

        di = np.sqrt(np.multiply((station_X - mobile_X), (station_X - mobile_X)) + np.multiply((station_Y - mobile_Y),
                                                                                               (station_Y - mobile_Y)))
        he = np.abs(station_AH + station_BH - mobile_AH - 0.5 * mobile_BH)
        ht = np.multiply(di, np.tan((theta_A + theta_B) * np.pi / 180))
        dis = np.sqrt(np.multiply(di, di) + np.multiply(he, he))
        dh = abs(ht - he)

        n = len(index_names)
        index_label = np.zeros((len(station_Index), n))

        point_dic = get_kv_point2prop(mobile_X, mobile_Y, mobile_AH, mobile_BH, mobile_Iindex)

        count = {}
        for i in range(len(station_X)):
            # print(station_X[i], station_Y[i], mobile_X[i], mobile_Y[i])
            # print(i)
            load_line = get_road_point([0, 0], [int(mobile_X[i] - station_X[i]), int(mobile_Y[i] - station_Y[i])], 5)
            if len(load_line) not in count:
                count[len(load_line)] = 1
            else:
                count[len(load_line)] += 1
            for j in load_line:
                # print(j)
                point = (station_X[i] + j[0], station_Y[i] + j[1])
                if point in point_dic:
                    # print(point)
                    index_label[i][point_dic[point][2]] += 1

        df_data["Index Weight"] = np.dot(index_label, np.array(index_weight).reshape(-1, 1))
        df_data["DealtaHeight"] = dh
        df_data["Distance"] = dis
        df_data["Frequency Band"] = np.log2(df_data["Frequency Band"])

        litheta = abs(theta - theta_AZ)
        litheta[litheta > 180] *= -1
        litheta[litheta < -180] += 360

        df_data["LineTheta"] = litheta * np.pi / 180

        # for i in range(n):
        #     # print(index_names[i])
        #     infom = index_label[:, i].reshape(-1, 1)
        #     # print(infom.shape)
        #     df_data[index_names[i]] = infom

        df_data = df_data.drop(columns=["Cell Index", "Azimuth", "Cell X", "Cell Y", "Height", "Electrical Downtilt",
                                        "Mechanical Downtilt", "Cell Altitude", "Cell Clutter Index",
                                        "X", "Y", "Altitude", "Building Height", "Clutter Index"
                                        ])

        # "oceans", "wetlands", "suburban open areas", "forest", "rural", "CBD"
        filesDatas = np.array(df_data,dtype=np.float32).reshape(-1, 7)
        # filesDatas = normalize(filesDatas) * 100
        preprocessed_data['myInput'] = filesDatas
        print("preprocessed_data[\'myInput\'].shape = ", preprocessed_data['myInput'].shape)

        return preprocessed_data

    def _postprocess(self, data):
        infer_output = {"RSRP": []}
        for output_name, results in data.items():
            print(output_name, np.array(results).shape)
            infer_output["RSRP"] = results
        return infer_output