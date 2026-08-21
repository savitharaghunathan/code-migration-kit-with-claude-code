// SPDX-License-Identifier: Apache-2.0
using Example;  // in-repo: edge C.cs -> A.cs (closes the cycle)

namespace Example.Models;

public class C
{
    public int Compute()
    {
        return new A().Run().Length;
    }
}
