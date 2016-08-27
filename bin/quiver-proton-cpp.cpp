/*
 *
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 * 
 *   http://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 *
 */

#include <iostream>

int main(int argc, char** argv) {
    std::string work_dir = argv[1];
    std::string mode = argv[2];
    std::string operation = argv[3];
    std::string host_port = argv[4];
    std::string address = argv[5];
    int transfers = std::atoi(argv[6]);
    int body_bytes = std::atoi(argv[7]);
    int credit_window = std::atoi(argv[8]);

    std::cerr << work_dir << std::endl;
    std::cerr << mode << std::endl;
    std::cerr << operation << std::endl;
    std::cerr << host_port << std::endl;
    std::cerr << address << std::endl;
    std::cerr << transfers << std::endl;
    std::cerr << body_bytes << std::endl;
    std::cerr << credit_window << std::endl;
}
