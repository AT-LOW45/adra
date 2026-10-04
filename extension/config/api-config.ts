import axios, { CreateAxiosDefaults } from "axios";
import * as vscode from "vscode";

const config = vscode.workspace.getConfiguration("adra");
const ragBaseUrl = config.get<string>("ragEndpoint");

const axiosConfig: CreateAxiosDefaults = {
	baseURL: ragBaseUrl,
	timeout: 5000,
};

const ragApi = axios.create(axiosConfig);

export default ragApi;
