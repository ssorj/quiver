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
    std::string output_dir = argv[1];
    std::string mode = argv[2];
    std::string domain = argv[4];
    std::string path = argv[5];
    std::string operation = argv[3];
    int messages = std::atoi(argv[6]);
    int bytes = std::atoi(argv[7]);
    int credit = std::atoi(argv[8]);

    std::cerr << output_dir << std::endl;
    std::cerr << mode << std::endl;
    std::cerr << domain << std::endl;
    std::cerr << path << std::endl;
    std::cerr << operation << std::endl;
    std::cerr << messages << std::endl;
    std::cerr << bytes << std::endl;
    std::cerr << credit << std::endl;
}
