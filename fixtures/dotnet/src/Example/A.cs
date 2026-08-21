// SPDX-License-Identifier: Apache-2.0
using System.Collections.Generic;  // stdlib: must NOT appear as an edge
using Example.Services;            // in-repo: edge A.cs -> Services/B.cs
using Example.Util;                // in-repo: edge A.cs -> Util/Helper.cs

namespace Example;

public class A
{
    public string Run()
    {
        return new List<string> { new B().Value(), Helper.Format("ok") }.ToString();
    }
}
