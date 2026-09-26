#pragma once

#include "CoreMinimal.h"

namespace VP
{
	// Lecture little-endian dans un tampon mémoire
	struct FReader
	{
		const uint8* Data;
		int64 Size;
		int64 Pos = 0;
		bool bError = false;

		explicit FReader(const TArray<uint8>& In)
			: Data(In.GetData()), Size(In.Num())
		{
		}

		bool Need(int64 N)
		{
			if (bError || Pos + N > Size)
			{
				bError = true;
				return false;
			}
			return true;
		}

		template <typename T>
		T Get()
		{
			T Value{};
			if (Need(sizeof(T)))
			{
				FMemory::Memcpy(&Value, Data + Pos, sizeof(T));
				Pos += sizeof(T);
			}
			return Value;
		}

		void Bytes(void* Dest, int64 N)
		{
			if (N <= 0)
			{
				return;
			}
			if (Need(N))
			{
				FMemory::Memcpy(Dest, Data + Pos, N);
				Pos += N;
			}
		}

		FString String16()
		{
			const uint16 Len = Get<uint16>();
			TArray<uint8> Buffer;
			Buffer.SetNumZeroed(Len + 1);
			Bytes(Buffer.GetData(), Len);
			return FString(UTF8_TO_TCHAR(reinterpret_cast<const ANSICHAR*>(Buffer.GetData())));
		}
	};

	inline uint32 ReadU32(const TArray<uint8>& Data, int32 Offset)
	{
		uint32 Value = 0;
		if (Data.Num() >= Offset + 4)
		{
			FMemory::Memcpy(&Value, Data.GetData() + Offset, 4);
		}
		return Value;
	}

	inline float ReadF32(const TArray<uint8>& Data, int32 Offset)
	{
		float Value = 0.f;
		if (Data.Num() >= Offset + 4)
		{
			FMemory::Memcpy(&Value, Data.GetData() + Offset, 4);
		}
		return Value;
	}
}
