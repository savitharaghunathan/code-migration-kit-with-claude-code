// SPDX-License-Identifier: Apache-2.0
package com.example;

import com.example.A;  // in-repo: edge C.java -> A.java (closes the cycle)

public class C {
    public int compute() {
        return new A().run().length();
    }
}
