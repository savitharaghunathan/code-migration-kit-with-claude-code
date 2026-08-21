// SPDX-License-Identifier: Apache-2.0
using Newtonsoft.Json;   // third-party: must NOT appear as an edge (never compiled, only parsed)
using Example.Models;    // in-repo: edge B.cs -> Models/C.cs

namespace Example.Services;

public class B
{
    public string Value()
    {
        return new C().Compute().ToString();
    }
}
